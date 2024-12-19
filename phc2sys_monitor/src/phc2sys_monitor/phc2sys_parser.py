from dataclasses import dataclass
from enum import Enum
import re

from journal_monitor.journal_monitor import JournalEntry


class SyncState(Enum):
    SERVO_UNLOCKED = 0
    SERVO_JUMP = 1
    SERVO_LOCKED = 2
    SERVO_LOCKED_STABLE = 3


################################
# PHC2SYS state machine
################################


@dataclass
class Uninitialized:
    def parse(self, entry: JournalEntry):
        return Running().parse(entry)


@dataclass
class Running:
    message_re = r"\[(?P<monotonic_time_s>[0-9]+\.[0-9]+)\]\s+(?P<message>.*)\s*$"
    offset_re = r"(?P<dst_clock>\w+)\s+(?P<src_clock_type>\w+)\s+offset\s+(?P<offset_ns>[+-]?\d+)\s+s(?P<sync_state>[0-3])\s+freq\s+(?P<freq_offset_ppb>[+-]?\d+)(?:\s+delay\s+(?P<delay_ns>[+-]?\d+))?"

    def _parse_offset(self, message: str):
        m = re.match(Running.offset_re, message)
        if not m:
            return False

        src_clock = m["src_clock_type"]
        dst_clock = m["dst_clock"]
        offset_ns = int(m["offset_ns"])
        sync_state = SyncState(int(m["sync_state"]))
        delay_ns = int(m.groupdict().get("delay_ns", "0"))

        print(
            f"Clock {dst_clock} is {sync_state.name} with an offset of {offset_ns / 1e9:.3f} s and a delay of {delay_ns / 1e6:.3f} ms to a {src_clock} clock."
        )
        return True

    def parse(self, entry: JournalEntry):
        m: re.Match = re.match(Running.message_re, entry.message)
        if not m:
            return self

        message: str = m["message"]
        if self._parse_offset(message):
            return self
        return self


State = Uninitialized | Running


class Phc2SysParser:
    def __init__(self):
        self.state = Uninitialized()

    start_stop_re = r"(?:Started|Stopped|Stopping)"

    def step_state_machine(self, entry: JournalEntry):
        old_state = self.state
        self.state = self.parse(entry)

        if old_state != self.state:
            print(f"Changed from {old_state} to {self.state} on:")

    def parse(self, entry: JournalEntry):
        if entry.unit.startswith("init.scope") or entry.unit.startswith("systemd"):
            if re.match(Phc2SysParser.start_stop_re, entry.message):
                return Uninitialized()
            return self.state

        if not entry.unit.startswith("phc2sys"):
            return self.state

        return self.state.parse(entry)
