from diag_worker.monitor_task import MonitorTask
from diag_worker.systemd_util import does_unit_exist, get_command_line, get_unit_pid
from journal_monitor.console_polling_journal_monitor import ConsolePollingJournalMonitor
from linuxptp_monitor.phc2sys_instance import Phc2SysConfig, Phc2SysRunningState
from linuxptp_monitor.state_machine import (
    SystemdUnitStateChange,
    SystemdUnitStateMachine,
)
from sync_tooling_msgs.graph_update_pb2 import GraphUpdate
from sync_tooling_msgs.phc2sys_update_pb2 import Phc2SysUpdate


class Phc2SysMonitorTask(MonitorTask):
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

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(hostname={self.hostname_}, unit={self.unit_name_})"

    def phc2sys_to_graph_updates(self, state_change: SystemdUnitStateChange):
        Uninitialized = SystemdUnitStateMachine.Uninitialized  # noqa: N806

        match (state_change.old_state, state_change.new_state):
            case (Uninitialized(), Uninitialized()):
                raise AssertionError()
            case (_, Phc2SysRunningState() as s):
                src_id = s.config.source_clock

                for dst_id, state in s.dst_clock_states.items():
                    yield GraphUpdate(
                        phc2sys_update=Phc2SysUpdate(
                            src=src_id,
                            dst=dst_id,
                            clock_state=state,
                        )
                    )
            case _:
                # TODO(mojomex): add feature to remove links from sync graph
                pass

    async def poll(self):
        journal_entries = self.journal_monitor.poll()
        for event in self.state_machine.consume(journal_entries):
            match event:
                case GraphUpdate() as update:
                    yield update
                case SystemdUnitStateChange() as state_change:
                    for update in self.phc2sys_to_graph_updates(state_change):
                        yield update
