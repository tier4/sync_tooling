import asyncio
import socket

from diag_worker.monitor_task import MonitorTask
from diag_worker.phc2sys_monitor_task import Phc2SysMonitorTask
from diag_worker.ptp4l_monitor_task import Ptp4lMonitorTask, Ptp4lRunningState
from aiostream.stream import merge

from linuxptp_monitor.phc2sys_instance import Phc2SysRunningState
from pmc_monitor.pmc_monitor import PmcStateChange
import rclpy
import rclpy.qos
from ros2_transport import JsonPublisher


def parse_list_parameter(ros2_parameter: rclpy.Parameter) -> list | None:
    match ros2_parameter.value:
        case [*items]:
            return items
        case _:
            return None


class DiagWorker:
    def __init__(self) -> None:
        hostname = socket.gethostname()
        if not hostname:
            raise RuntimeError("Could not determine hostname")

        self.node_ = rclpy.create_node(f"/sync_diag/worker/{hostname}")  # type: ignore
        self.publisher_ = JsonPublisher(self.node_, "/sync_diag/graph_updates", 10)

        ptp4l_units = self.node_.declare_parameter("ptp4l_units")
        phc2sys_units = self.node_.declare_parameter("phc2sys_units")

        ptp4l_units = parse_list_parameter(ptp4l_units)
        phc2sys_units = parse_list_parameter(phc2sys_units)

        if not ptp4l_units and not phc2sys_units:
            raise ValueError(
                "No PTP4L or PHC2SYS units given. At least one is required."
            )

        self.monitors_: list[MonitorTask] = []

        if ptp4l_units:
            for unit_name in ptp4l_units:
                self.monitors_.append(Ptp4lMonitorTask(unit_name, hostname))

        if phc2sys_units:
            for unit_name in phc2sys_units:
                self.monitors_.append(Phc2SysMonitorTask(unit_name, hostname))

    def handle_pmc_state_change(self, s: PmcStateChange):
        pass

    def handle_phc2sys_state_change(self, s: Phc2SysRunningState):
        pass

    def handle_ptp4l_state_change(self, s: Ptp4lRunningState):
        pass

    def handle_unknown(self, other):
        pass

    def handle_event(self, event):
        match event:
            case PmcStateChange():
                self.handle_pmc_state_change(event)
            case Phc2SysRunningState():
                self.handle_phc2sys_state_change(event)
            case Ptp4lRunningState():
                self.handle_ptp4l_state_change(event)
            case other:
                self.handle_unknown(other)

    async def run(self):
        combined = merge(*[m.run_loop(1) for m in self.monitors_])
        async with combined.stream() as events:
            async for event in events:
                self.handle_event(event)


def main():
    rclpy.init()

    diag_worker = DiagWorker()
    asyncio.run(diag_worker.run())
