import asyncio
import logging
import socket
import time
from argparse import ArgumentParser

from aiostream.stream import merge

from diag_worker.monitor_task import MonitorTask
from diag_worker.phc2sys_monitor_task import Phc2SysMonitorTask
from diag_worker.ptp4l_monitor_task import Ptp4lMonitorTask
from http_transport import HttpClient


class DiagWorker:
    def __init__(
        self,
        master_ip: str,
        master_port: int,
        ptp4l_units: list[str],
        phc2sys_units: list[str],
    ) -> None:
        hostname = socket.gethostname()
        if not hostname:
            raise RuntimeError("Could not determine hostname")

        self.client_ = HttpClient(f"http://{master_ip}:{master_port}/update_graph")

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
                self.client_.send(event)
            print(f"published {count} graph updates")


def main():
    parser = ArgumentParser()
    parser.add_argument("master_ip")
    parser.add_argument("--master_port", "-p", type=int, default=16161)
    parser.add_argument("--ptp4l-units", "-4", nargs="+")
    parser.add_argument("--phc2sys-units", "-2", nargs="+")
    args = parser.parse_args()

    while True:
        diag_worker = DiagWorker(
            args.master_ip, args.master_port, args.ptp4l_units, args.phc2sys_units
        )

        try:
            asyncio.run(diag_worker.run())
        except Exception:
            logging.exception("Encountered a problem")
            print("Backing off and restarting")
            time.sleep(5)
