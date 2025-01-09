from abc import ABC, abstractmethod
import asyncio


class MonitorTask(ABC):
    @abstractmethod
    def poll(self):
        raise NotImplementedError()

    async def run_loop(self, period_s: float):
        self._running = True
        print(f"{self.__class__.__name__}: Starting {1 / period_s:.0f} Hz monitor loop")

        while self._running:
            async for event in self.poll():
                yield event
            await asyncio.sleep(period_s)  # type: ignore

    def stop(self):
        self._running = False
