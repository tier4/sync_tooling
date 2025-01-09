from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List


@dataclass
class JournalEntry:
    system_timestamp: datetime
    monotonic_timestamp_us: int | None
    cursor: str | None
    unit: str
    message: str | None


class JournalMonitor(ABC):
    """
    Provides an interface to subscribe to systemd journal entries.
    """

    @abstractmethod
    def only_current_boot(self) -> "JournalMonitor":
        raise NotImplementedError()

    @abstractmethod
    def only_systemd_unit(self, unit_name: str) -> "JournalMonitor":
        raise NotImplementedError()

    @abstractmethod
    def poll(self) -> List[JournalEntry]:
        raise NotImplementedError()
