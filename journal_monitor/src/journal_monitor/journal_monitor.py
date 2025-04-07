from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List


@dataclass
class JournalEntry:
    class Priority(Enum):
        Emergency = 0
        Alert = 1
        Critical = 2
        Error = 3
        Warning = 4
        Notice = 5
        Info = 6
        Debug = 7

    system_timestamp: datetime
    monotonic_timestamp_us: int | None
    cursor: str | None
    unit: str
    message: str | None
    priority: Priority | None


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
    def only_from_seconds_ago(self, seconds: int) -> "JournalMonitor":
        raise NotImplementedError()

    @abstractmethod
    def poll(self) -> List[JournalEntry]:
        raise NotImplementedError()
