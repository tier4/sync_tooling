"""Abstract base class for monitor tasks."""

import asyncio
import time
from abc import ABC, abstractmethod


class MonitorTask(ABC):
    """Abstract base class for periodic monitoring tasks."""

    @abstractmethod
    def poll(self):
        """Poll for updates, yielding graph update events."""
        raise NotImplementedError()

    async def run_loop(self, period_s: float):
        """Run the polling loop at the specified period."""
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
        """Stop the monitoring loop."""
        self._running = False
