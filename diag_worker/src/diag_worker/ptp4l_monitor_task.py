from diag_worker.monitor_task import MonitorTask
from diag_worker.systemd_util import get_command_line, get_unit_pid
from journal_monitor.console_polling_journal_monitor import ConsolePollingJournalMonitor
from linuxptp_monitor.ptp4l_instance import (
    Ptp4lConfig,
    Ptp4lRunningState,
)
from linuxptp_monitor.state_machine import SystemdUnitStateMachine
from pmc_monitor.pmc_monitor import PmcMonitor
from aiostream.stream import merge


class Ptp4lMonitorTask(MonitorTask):
    def __init__(self, unit_name: str):
        self.journal_monitor = (
            ConsolePollingJournalMonitor()
            .only_current_boot()
            .only_systemd_unit(unit_name)
        )

        self.pmc_monitor_local: PmcMonitor | None = None
        self.pmc_monitors_remote: list[PmcMonitor] = []

        def ptp4l_state_factory():
            pid = get_unit_pid(unit_name)
            cmdline = get_command_line(pid)
            config = Ptp4lConfig(cmdline)
            self._create_pmc_monitors(config)
            return Ptp4lRunningState(config)

        def on_stopped(_):
            self._reset_pmc_monitors()

        self.state_machine = SystemdUnitStateMachine(
            ptp4l_state_factory, on_stopped, unit_name
        )

    def _create_pmc_monitors(self, config: Ptp4lConfig):
        self._reset_pmc_monitors()

        local_target_socket = config.uds_address
        self.pmc_monitor_local = PmcMonitor(["-u", "-s", local_target_socket])

        for port in config.ports:
            self.pmc_monitors_remote.append(
                PmcMonitor([config.network_transport.to_flag(), "-i", port])
            )

    def _reset_pmc_monitors(self):
        if self.pmc_monitor_local is not None:
            self.pmc_monitor_local.stop()
        for monitor in self.pmc_monitors_remote:
            monitor.stop()

        self.pmc_monitor_local = None
        self.pmc_monitors_remote = []

    async def poll(self):
        journal_entries = self.journal_monitor.poll()
        for entry in journal_entries:
            yield self.state_machine.consume(entry)

        pmc_event_streams = [pmc.poll() for pmc in self.pmc_monitors_remote]
        if self.pmc_monitor_local is not None:
            pmc_event_streams.append(self.pmc_monitor_local.poll())

        combined = merge(*pmc_event_streams)
        async with combined.stream() as events:
            async for event in events:
                yield event

    def stop(self):
        super().stop()
        self._reset_pmc_monitors()
