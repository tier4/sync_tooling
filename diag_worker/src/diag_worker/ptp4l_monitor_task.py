from diag_worker.monitor_task import MonitorTask
from diag_worker.systemd_util import does_unit_exist, get_command_line, get_unit_pid
from journal_monitor.console_polling_journal_monitor import ConsolePollingJournalMonitor
from linuxptp_monitor.ptp4l_instance import (
    Ptp4lConfig,
    Ptp4lRunningState,
)
from linuxptp_monitor.state_machine import (
    SystemdUnitStateChange,
    SystemdUnitStateMachine,
)
from pmc_monitor.pmc_monitor import PmcMonitor
from pmc_monitor.pmc_protocol import CurrentDataSet, DefaultDataSet, ParentDataSet
from pmc_monitor.ptp_instance import PtpInstance
from sync_tooling_msgs.clock_alias_update_pb2 import ClockAliasUpdate
from sync_tooling_msgs.clock_id_pb2 import ClockId
from sync_tooling_msgs.clock_master_update_pb2 import ClockMasterUpdate
from sync_tooling_msgs.graph_update_pb2 import GraphUpdate
from sync_tooling_msgs.port_id_pb2 import PortId
from sync_tooling_msgs.port_state import port_state_value
from sync_tooling_msgs.port_state_update_pb2 import PortStateUpdate
from sync_tooling_msgs.ptp_clock_id_pb2 import PtpClockId
from sync_tooling_msgs.ptp_parent_update_pb2 import PtpParentUpdate


class Ptp4lMonitorTask(MonitorTask):
    def __init__(self, unit_name: str, hostname: str):
        if not does_unit_exist(unit_name):
            raise FileNotFoundError(f"Unit {unit_name} was not found on this system")

        self.journal_monitor = (
            ConsolePollingJournalMonitor()
            .only_from_seconds_ago(5)
            .only_systemd_unit(unit_name)
        )

        self.unit_name_ = unit_name
        self.hostname_ = hostname
        self.pmc_monitor: PmcMonitor | None = None
        self.ptp4l_clock_id: ClockId | None = None
        self.domain_id: int | None = None

        def ptp4l_state_factory():
            pid = get_unit_pid(unit_name)

            if pid is None:
                print(f"PTP4L unit {unit_name} is not running")
                return None

            cmdline = get_command_line(pid)
            config = Ptp4lConfig(cmdline)
            self.ptp4l_clock_id = config.clock
            self._create_pmc_monitor(config)
            print(
                f"PTP4L unit {unit_name} is running with clock ID {self.ptp4l_clock_id}"
            )
            return Ptp4lRunningState(config)

        def on_stopped(_):
            print(f"PTP4L unit {unit_name} is stopped")
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
                "-b",
                "0",
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

    def pmc_to_graph_updates(self, inst: PtpInstance):
        if self.domain_id is None:
            raise AssertionError()

        if not isinstance(inst.default_ds, DefaultDataSet):
            return

        assert inst.default_ds.domainNumber == self.domain_id
        clock_id: ClockId = ClockId(
            ptp_clock_id=PtpClockId(id=inst.id(), domain=self.domain_id)
        )

        if inst.is_local_instance:
            assert self.ptp4l_clock_id is not None
            yield GraphUpdate(
                clock_alias_update=ClockAliasUpdate(
                    aliases=[clock_id, self.ptp4l_clock_id]
                )
            )

        parent_port_id: PortId | None = None

        if isinstance(inst.parent_ds, ParentDataSet):
            pds = inst.parent_ds

            if isinstance(inst.current_ds, CurrentDataSet):
                yield GraphUpdate(
                    clock_master_update=ClockMasterUpdate(
                        clock_id=clock_id,
                        master=ClockId(
                            ptp_clock_id=PtpClockId(
                                id=pds.grandmasterIdentity, domain=self.domain_id
                            ),
                        ),
                        master_offset_ns=int(inst.current_ds.offsetFromMaster),
                    )
                )

            parent_clock_id = pds.parentPortIdentity.clock_id
            parent_port_num = pds.parentPortIdentity.port_number
            parent_port_id = PortId(
                clock_id=ClockId(
                    ptp_clock_id=PtpClockId(id=parent_clock_id, domain=self.domain_id)
                ),
                port_number=parent_port_num,
                ptp_domain=self.domain_id,
            )

        for port in inst.ports.values():
            port_id = PortId(
                clock_id=clock_id,
                port_number=port.port_ds.portIdentity.port_number,
                ptp_domain=self.domain_id,
            )
            if port.port_ds.portState == "SLAVE" and parent_port_id:
                yield GraphUpdate(
                    ptp_parent_update=PtpParentUpdate(
                        clock_id=clock_id, parent=parent_port_id
                    )
                )
            yield GraphUpdate(
                port_state_update=PortStateUpdate(
                    port_id=port_id, port_state=port_state_value(port.port_ds.portState)
                )
            )

    def ptp4l_to_graph_updates(self, state_change: SystemdUnitStateChange):
        return
        yield None

    async def poll(self):
        journal_entries = self.journal_monitor.poll()
        for event in self.state_machine.consume(journal_entries):
            match event:
                case GraphUpdate() as update:
                    yield update
                case SystemdUnitStateChange() as state_change:
                    for graph_update in self.ptp4l_to_graph_updates(state_change):
                        yield graph_update
                case _:
                    print(f"Got unrecognized event of type {type(event)}: {event}")

        if self.pmc_monitor is not None:
            async for state_change in self.pmc_monitor.poll():
                print(f"got state change: {state_change.__class__.__name__}")
                for graph_update in self.pmc_to_graph_updates(state_change):
                    yield graph_update

    def stop(self):
        super().stop()
        self._reset_pmc_monitor()
