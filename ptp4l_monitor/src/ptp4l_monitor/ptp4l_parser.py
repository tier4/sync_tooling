from dataclasses import dataclass
from enum import Enum
import re
from typing import Dict

from journal_monitor.journal_monitor import JournalEntry


# Adapted from fsm.h of LinuxPTP
class PortState(Enum):
    INITIALIZING = 1
    FAULTY = 2
    DISABLED = 3
    LISTENING = 4
    PRE_MASTER = 5
    MASTER = 6
    PASSIVE = 7
    UNCALIBRATED = 8
    SLAVE = 9
    GRAND_MASTER = 10


class SyncState(Enum):
    SERVO_UNLOCKED = 0
    SERVO_JUMP = 1
    SERVO_LOCKED = 2
    SERVO_LOCKED_STABLE = 3


################################
# PTP4L state machine
################################


@dataclass
class Uninitialized:
    def parse(self, entry: JournalEntry):
        return Running({}).parse(entry)


@dataclass
class Running:
    port_states: Dict[int, PortState]

    message_re = r"\[(?P<monotonic_time_s>[0-9]+\.[0-9]+)\]\s+(?P<message>.*)\s*$"
    port_re = r"port\s+(?P<port_id>[0-9]+):\s+(?P<port_message>.*)\s*$"
    state_change_re = (
        r"(?P<from_state>\w+)\s+to\s+(?P<to_state>\w+)\s+on\s+(?P<event>\w+)\s*$"
    )
    master_offset_re = r"master offset (?P<offset_ns>[+-]?\d+)\s+s(?P<sync_state>[0-3])\s+freq\s+(?P<freq_offset_ppb>[+-]?\d+)\s+path delay\s+(?P<path_delay_ns>[+-]?\d+)"

    def _parse_port_state_change(self, message: str):
        m = re.match(Running.port_re, message)
        if not m:
            return False
        port_id = int(m["port_id"])
        port_message = m["port_message"]

        m = re.match(Running.state_change_re, port_message)
        if not m:
            return True

        from_state = m["from_state"]
        to_state = m["to_state"]
        event = m["event"]

        print(f"Port {port_id} changed from {from_state} to {to_state} on {event}")
        self.port_states[port_id] = to_state

        return True

    def _parse_master_offset(self, message: str):
        m = re.match(Running.master_offset_re, message)
        if not m:
            return False

        offset_ns = int(m["offset_ns"])
        sync_state = SyncState(int(m["sync_state"]))
        path_delay_ns = int(m["path_delay_ns"])

        print(
            f"Clock is {sync_state.name} with an offset of {offset_ns / 1e9:.3f} s and a path delay of {path_delay_ns / 1e6:.3f} ms"
        )
        return True

    def parse(self, entry: JournalEntry):
        m: re.Match = re.match(Running.message_re, entry.message)
        if not m:
            return self

        message: str = m["message"]
        if self._parse_master_offset(message):
            return self
        if self._parse_port_state_change(message):
            return self

        return self


State = Uninitialized | Running


class Ptp4lParser:
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
            if re.match(Ptp4lParser.start_stop_re, entry.message):
                return Uninitialized()
            return self.state

        if not entry.unit.startswith("ptp4l"):
            return self.state

        return self.state.parse(entry)
