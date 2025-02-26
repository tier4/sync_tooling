from sync_graph import ClockMasterUpdate, Phc2SysUpdate
from diag_tree import diagnose
from diag_worker.monitor_task import MonitorTask
from diag_worker.systemd_util import does_unit_exist, get_command_line, get_unit_pid
from diag_worker.util import linuxptp_to_graph_clock_id
from journal_monitor.console_polling_journal_monitor import ConsolePollingJournalMonitor
from linuxptp_monitor.phc2sys_instance import Phc2SysConfig, Phc2SysRunningState
from linuxptp_monitor.state_machine import (
    SystemdUnitStateChange,
    SystemdUnitStateMachine,
)
from sync_tooling_msgs.graph_update_pb2 import GraphUpdate


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

    def to_graph_updates(self, state_change: SystemdUnitStateChange):
        Uninitialized = SystemdUnitStateMachine.Uninitialized

        match (state_change.old_state, state_change.new_state):
            case (Uninitialized(), Uninitialized()):
                assert False
            case (old, Phc2SysRunningState() as s):
                is_init = isinstance(old, Uninitialized)
                src_id = linuxptp_to_graph_clock_id(
                    s.config.source_clock, self.hostname_
                )

                for clock_id, state in s.dst_clock_states.items():
                    dst_id = linuxptp_to_graph_clock_id(clock_id, self.hostname_)

                    if is_init:
                        yield GraphUpdate(
                            clock_master_update=ClockMasterUpdate(
                                clock_id=dst_id, master=src_id
                            )
                        )
                    yield GraphUpdate(
                        phc2sys_update=Phc2SysUpdate(
                            src=src_id,
                            dst=dst_id,
                            diag=diagnose(state),
                        )
                    )
            case _:
                # TODO(mojomex): add feature to remove links from sync graph
                pass

    async def poll(self):
        journal_entries = self.journal_monitor.poll()
        for entry in journal_entries:
            state_change = self.state_machine.consume(entry)
            if state_change is not None:
                for update in self.to_graph_updates(state_change):
                    yield update
