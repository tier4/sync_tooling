import asyncio
import socket

from diag_worker.monitor_task import MonitorTask
from diag_worker.phc2sys_monitor_task import Phc2SysMonitorTask
from diag_worker.ptp4l_monitor_task import Ptp4lMonitorTask
from aiostream.stream import merge

import rclpy
import rclpy.parameter
import rclpy.qos
from ros2_transport import JsonPublisher


class DiagWorker:
    def __init__(self) -> None:
        hostname = socket.gethostname()
        if not hostname:
            raise RuntimeError("Could not determine hostname")

        self.node_ = rclpy.create_node(hostname, namespace="/sync_diag/worker")  # type: ignore
        self.publisher_ = JsonPublisher(self.node_, "/sync_diag/graph_updates", 10)

        ptp4l_units = self.node_.declare_parameter(
            "watch.ptp4l.systemd_units", rclpy.parameter.Parameter.Type.STRING_ARRAY
        )
        phc2sys_units = self.node_.declare_parameter(
            "watch.phc2sys.systemd_units", rclpy.parameter.Parameter.Type.STRING_ARRAY
        )

        ptp4l_units = list(ptp4l_units.get_parameter_value().string_array_value)
        phc2sys_units = list(phc2sys_units.get_parameter_value().string_array_value)

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

    async def run(self):
        combined = merge(*[m.run_loop(1) for m in self.monitors_])
        async with combined.stream() as events:
            async for event in events:
                print(f"got graph update: {event}")
                self.publisher_.publish(event)


def main():
    rclpy.init()

    diag_worker = DiagWorker()
    asyncio.run(diag_worker.run())
