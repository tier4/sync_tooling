from diag_tree import diagnose
from pmc_monitor.pmc_protocol import ParentDataSet
from sync_graph import (
    ClockAliasUpdate,
    ClockId,
    PortId,
    PtpClockId,
    ClockMasterUpdate,
    PtpParentUpdate,
    PtpPortStateUpdate,
)
from diag_worker.monitor_task import MonitorTask
from diag_worker.systemd_util import does_unit_exist, get_command_line, get_unit_pid
from diag_worker.util import linuxptp_to_graph_clock_id
from journal_monitor.console_polling_journal_monitor import ConsolePollingJournalMonitor
from linuxptp_monitor.ptp4l_instance import (
    Ptp4lConfig,
    Ptp4lRunningState,
)
from linuxptp_monitor.state_machine import SystemdUnitStateMachine
from pmc_monitor.pmc_monitor import PmcMonitor, PmcStateChange


class Ptp4lMonitorTask(MonitorTask):
    def __init__(self, unit_name: str, hostname: str):
        if not does_unit_exist(unit_name):
            raise FileNotFoundError(f"Unit {unit_name} was not found on this system")

        self.journal_monitor = (
            ConsolePollingJournalMonitor()
            .only_current_boot()
            .only_systemd_unit(unit_name)
        )

        self.unit_name_ = unit_name
        self.hostname_ = hostname
        self.pmc_monitor: PmcMonitor | None = None
        self.ptp4l_clock_id: ClockId | None = None
        self.domain_id: int | None = None

        def ptp4l_state_factory():
            pid = get_unit_pid(unit_name)
            cmdline = get_command_line(pid)
            config = Ptp4lConfig(cmdline)
            self.ptp4l_clock_id = linuxptp_to_graph_clock_id(
                config.clock, self.hostname_
            )
            self._create_pmc_monitor(config)
            return Ptp4lRunningState(config)

        def on_stopped(_):
            self.ptp4l_clock_id = None
            self._reset_pmc_monitor()

        self.state_machine = SystemdUnitStateMachine(
            ptp4l_state_factory, on_stopped, unit_name
        )

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(hostname={self.hostname_}, unit={self.unit_name_})"

    def _create_pmc_monitor(self, config: Ptp4lConfig):
        self._reset_pmc_monitor()
        print(
            f"Starting PMC monitor with server={config.uds_address}, transport={hex(config.transport_specific)}, domain={config.config['global']['domainNumber']}"
        )
        self.domain_id = int(config.config["global"]["domainNumber"])
        self.pmc_monitor = PmcMonitor(
            [
                "-u",
                "-s",
                config.uds_address,
                "-t",
                hex(config.transport_specific),
                "-d",
                str(self.domain_id),
            ]
        )

    def _reset_pmc_monitor(self):
        if self.pmc_monitor is not None:
            print("Stopping PMC monitor")
            self.pmc_monitor.stop()
        self.pmc_monitor = None
        self.domain_id = None

    def pmc_to_graph_updates(self, state_change: PmcStateChange):
        if state_change.new_state is None:
            return

        if self.domain_id is None:
            assert False

        inst = state_change.new_state
        clock_id: PtpClockId = PtpClockId(inst.id())

        if inst.is_local_instance:
            assert self.ptp4l_clock_id is not None
            yield ClockAliasUpdate({clock_id, self.ptp4l_clock_id})

        parent_port_id: PortId | None = None

        if isinstance(inst.parent_ds, ParentDataSet):
            pds = inst.parent_ds
            yield ClockMasterUpdate(clock_id, PtpClockId(pds.grandmasterIdentity))

            parent_clock_id = pds.parentPortIdentity.clock_id
            parent_port_num = pds.parentPortIdentity.port_number
            parent_port_id = PortId(
                PtpClockId(parent_clock_id), parent_port_num, self.domain_id
            )

        for port in inst.ports.values():
            port_id = PortId(
                clock_id, port.port_ds.portIdentity.port_number, self.domain_id
            )
            if port.port_ds.portState == "SLAVE" and parent_port_id:
                yield PtpParentUpdate(parent_port_id, clock_id)
            yield PtpPortStateUpdate(port_id, diagnose(port.port_stats))

    async def poll(self):
        journal_entries = self.journal_monitor.poll()
        for entry in journal_entries:
            state_change = self.state_machine.consume(entry)
            if state_change is not None:
                # TODO(mojomex): decide what info is needed from PTP4L
                print(f"got event: {state_change.__class__.__name__}")
                pass

        if self.pmc_monitor is not None:
            async for event in self.pmc_monitor.poll():
                print(f"got event: {event.__class__.__name__}")
                for graph_update in self.pmc_to_graph_updates(event):
                    yield graph_update

    def stop(self):
        super().stop()
        self._reset_pmc_monitor()
