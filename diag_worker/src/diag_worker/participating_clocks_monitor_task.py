import itertools

from diag_worker.monitor_task import MonitorTask
from diag_worker.phc2sys_monitor_task import Phc2SysMonitorTask
from diag_worker.ptp4l_monitor_task import Ptp4lMonitorTask
from linuxptp_monitor.phc2sys_instance import Phc2SysRunningState
from linuxptp_monitor.phc_ctl_harness import get_time_ns
from linuxptp_monitor.ptp4l_instance import Ptp4lRunningState
from sync_tooling_msgs.clock_time_snapshot_pb2 import ClockTimeSnapshot
from sync_tooling_msgs.graph_update_pb2 import GraphUpdate


class ParticipatingClocksMonitorTask(MonitorTask):
    def __init__(
        self,
        ptp4l_monitors: list[Ptp4lMonitorTask],
        phc2sys_monitors: list[Phc2SysMonitorTask],
    ):
        self.ptp4l_monitors = ptp4l_monitors
        self.phc2sys_monitors = phc2sys_monitors

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(ptp4l_monitors={self.ptp4l_monitors}, phc2sys_monitors={self.phc2sys_monitors})"

    def _get_participating_clocks(self):
        participating_clocks = set()

        for monitor in itertools.chain(self.ptp4l_monitors, self.phc2sys_monitors):
            match monitor.state_machine.state:
                case Ptp4lRunningState() | Phc2SysRunningState() as state:
                    participating_clocks |= state.config.get_participating_clocks()
                case _:
                    pass
        return participating_clocks

    async def poll(self):
        participating_clocks = self._get_participating_clocks()

        for clock in participating_clocks:
            clock_time_ns = get_time_ns(clock)
            yield GraphUpdate(
                clock_time_snapshot=ClockTimeSnapshot(
                    clock=clock,
                    time_ns=clock_time_ns,
                )
            )
