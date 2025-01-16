import asyncio
import socket

from diag_worker.monitor_task import MonitorTask
from diag_worker.phc2sys_monitor_task import Phc2SysMonitorTask
from diag_worker.ptp4l_monitor_task import Ptp4lMonitorTask
from aiostream.stream import merge

import rclpy
import rclpy.qos
from ros2_transport import JsonPublisher


async def run_loop(monitors: list[MonitorTask], pub: JsonPublisher):
    combined = merge(*[m.run_loop(1) for m in monitors])
    async with combined.stream() as events:
        async for event in events:
            pub.publish(event)


def parse_list_parameter(ros2_parameter: rclpy.Parameter) -> list | None:
    match ros2_parameter.value:
        case [*items]:
            return items
        case _:
            return None


def main():
    rclpy.init()

    hostname = socket.gethostname()
    if not hostname:
        raise RuntimeError("Could not determine hostname")

    node = rclpy.create_node(f"/sync_diag/worker/{hostname}")  # type: ignore
    publisher = JsonPublisher(node, "/sync_diag/graph_updates", 10)

    ptp4l_units = node.declare_parameter("ptp4l_units")
    phc2sys_units = node.declare_parameter("phc2sys_units")

    ptp4l_units = parse_list_parameter(ptp4l_units)
    phc2sys_units = parse_list_parameter(phc2sys_units)

    if not ptp4l_units and not phc2sys_units:
        raise ValueError("No PTP4L or PHC2SYS units given. At least one is required.")

    monitors: list[MonitorTask] = []

    if ptp4l_units:
        for unit_name in ptp4l_units:
            monitors.append(Ptp4lMonitorTask(unit_name))

    if phc2sys_units:
        for unit_name in phc2sys_units:
            monitors.append(Phc2SysMonitorTask(unit_name))

    asyncio.run(run_loop(monitors, publisher))
