import asyncio
import time
from abc import ABC, abstractmethod


class MonitorTask(ABC):
    @abstractmethod
    def poll(self):
        raise NotImplementedError()

    async def run_loop(self, period_s: float):
        self._running = True
        print(f"{self}: Starting {1 / period_s:.0f} Hz monitor loop")

        while self._running:
            t_start = time.monotonic()
            async for event in self.poll():
                yield event
            d_passed = time.monotonic() - t_start
            d_sleep = period_s - d_passed
            await asyncio.sleep(max(0, d_sleep))

    def stop(self):
        self._running = False
