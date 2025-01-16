from diag_worker.monitor_task import MonitorTask
from diag_worker.systemd_util import get_command_line, get_unit_pid
from journal_monitor.console_polling_journal_monitor import ConsolePollingJournalMonitor
from linuxptp_monitor.ptp4l_instance import (
    Ptp4lConfig,
    Ptp4lRunningState,
)
from linuxptp_monitor.state_machine import SystemdUnitStateMachine
from pmc_monitor.pmc_monitor import PmcMonitor


class Ptp4lMonitorTask(MonitorTask):
    def __init__(self, unit_name: str):
        self.journal_monitor = (
            ConsolePollingJournalMonitor()
            .only_current_boot()
            .only_systemd_unit(unit_name)
        )

        self.pmc_monitor: PmcMonitor | None = None

        def ptp4l_state_factory():
            pid = get_unit_pid(unit_name)
            cmdline = get_command_line(pid)
            config = Ptp4lConfig(cmdline)
            self._create_pmc_monitor(config)
            return Ptp4lRunningState(config)

        def on_stopped(_):
            self._reset_pmc_monitor()

        self.state_machine = SystemdUnitStateMachine(
            ptp4l_state_factory, on_stopped, unit_name
        )

    def _create_pmc_monitor(self, config: Ptp4lConfig):
        self._reset_pmc_monitor()

        self.pmc_monitor = PmcMonitor(["-u", "-s", config.uds_address])

    def _reset_pmc_monitor(self):
        if self.pmc_monitor is not None:
            self.pmc_monitor.stop()

        self.pmc_monitor = None
        self.pmc_monitors_remote = []

    async def poll(self):
        journal_entries = self.journal_monitor.poll()
        for entry in journal_entries:
            yield self.state_machine.consume(entry)

        if self.pmc_monitor is not None:
            async for event in self.pmc_monitor.poll():
                yield event

    def stop(self):
        super().stop()
        self._reset_pmc_monitor()
