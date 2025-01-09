from argparse import ArgumentParser
import asyncio

from diag_worker.monitor_task import MonitorTask
from diag_worker.phc2sys_monitor_task import Phc2SysMonitorTask
from diag_worker.ptp4l_monitor_task import Ptp4lMonitorTask
from aiostream.stream import merge


async def run_loop(monitors: list[MonitorTask]):
    combined = merge(*[m.run_loop(1) for m in monitors])
    async with combined.stream() as events:
        async for event in events:
            print(event)


def main():
    parser = ArgumentParser()

    parser.add_argument("--ptp4l-units", metavar="unit_name", nargs="+", default=[])
    parser.add_argument("--phc2sys-units", metavar="unit_name", nargs="+", default=[])

    args = parser.parse_args()
    if not args.ptp4l_units and not args.phc2sys_units:
        return

    monitors: list[MonitorTask] = []

    for unit_name in args.ptp4l_units:
        monitors.append(Ptp4lMonitorTask(unit_name))

    for unit_name in args.phc2sys_units:
        monitors.append(Phc2SysMonitorTask(unit_name))

    asyncio.run(run_loop(monitors))
