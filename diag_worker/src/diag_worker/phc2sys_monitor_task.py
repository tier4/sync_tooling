from diag_worker.monitor_task import MonitorTask
from diag_worker.systemd_util import get_command_line, get_unit_pid
from journal_monitor.console_polling_journal_monitor import ConsolePollingJournalMonitor
from linuxptp_monitor.phc2sys_instance import Phc2SysConfig, Phc2SysRunningState
from linuxptp_monitor.state_machine import SystemdUnitStateMachine


class Phc2SysMonitorTask(MonitorTask):
    def __init__(self, unit_name: str):
        self.journal_monitor = (
            ConsolePollingJournalMonitor()
            .only_current_boot()
            .only_systemd_unit(unit_name)
        )

        def phc2sys_factory():
            pid = get_unit_pid(unit_name)
            cmdline = get_command_line(pid)
            config = Phc2SysConfig(cmdline)
            return Phc2SysRunningState(config)

        def on_stopped(_):
            pass

        self.state_machine = SystemdUnitStateMachine(
            phc2sys_factory, on_stopped, unit_name
        )

    async def poll(self):
        journal_entries = self.journal_monitor.poll()
        for entry in journal_entries:
            yield self.state_machine.consume(entry)
