import asyncio
import logging
import socket
import time
from argparse import REMAINDER, ArgumentParser

import rclpy
from aiostream.stream import merge

from diag_worker.monitor_task import MonitorTask
from diag_worker.phc2sys_monitor_task import Phc2SysMonitorTask
from diag_worker.ptp4l_monitor_task import Ptp4lMonitorTask
from linuxptp_monitor.util import hostname_to_node_name
from ros2_transport.client import Ros2Client


class DiagWorker:
    def __init__(
        self,
        topic: str,
        ptp4l_units: list[str],
        phc2sys_units: list[str],
    ) -> None:
        hostname = socket.gethostname()
        if not hostname:
            raise RuntimeError("Could not determine hostname")

        node_name = hostname_to_node_name(hostname)
        self._node = rclpy.create_node(node_name, namespace="/sync_diag/workers")  # type: ignore
        self._client = Ros2Client(topic, node=self._node)

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
            count = 0
            async for event in events:
                count += 1
                self._client.send(event)
            print(f"published {count} graph updates")


def main():
    parser = ArgumentParser()
    parser.add_argument("--topic", "-t", default="/sync_diag/graph_updates")
    parser.add_argument("--ptp4l-units", "-4", nargs="*")
    parser.add_argument("--phc2sys-units", "-2", nargs="*")
    parser.add_argument(
        "--ros-args",
        nargs=REMAINDER,
        help="Arguments passed along to ROS 2. See https://docs.ros.org/en/rolling/How-To-Guides/Node-arguments.html for details.",
    )
    args = parser.parse_args()

    rclpy.init(args=args.ros_args)

    while True:
        diag_worker = DiagWorker(args.topic, args.ptp4l_units, args.phc2sys_units)

        try:
            asyncio.run(diag_worker.run())
        except Exception:
            logging.exception("Encountered a problem")
            print("Backing off and restarting")
            time.sleep(5)
