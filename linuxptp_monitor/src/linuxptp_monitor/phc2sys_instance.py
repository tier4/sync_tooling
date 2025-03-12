import re
from argparse import ArgumentParser, Namespace
from configparser import ConfigParser
from dataclasses import dataclass, field
from typing import Generator

from journal_monitor.journal_monitor import JournalEntry
from linuxptp_monitor.ethtool_harness import get_canonicalized_clock
from linuxptp_monitor.linuxptp_config import LinuxPtpConfig
from linuxptp_monitor.state_machine import Event, State
from sync_tooling_msgs.clock_id_pb2 import ClockId
from sync_tooling_msgs.servo_state_pb2 import ServoState
from sync_tooling_msgs.slave_clock_state_pb2 import SlaveClockState


@dataclass(init=False)
class Phc2SysConfig(LinuxPtpConfig):
    source_clock: ClockId
    dst_clocks: set[ClockId]
    clock_aliases: dict[str, ClockId]

    def add_args_app_specific(self, parser: ArgumentParser) -> None:
        parser.add_argument("-a", action="store_true", dest="do_auto_conf")
        parser.add_argument("-d", dest="pps_source")
        parser.add_argument("--uds_address", "-z")
        parser.add_argument("-s", dest="source_clock")
        parser.add_argument("-c", action="append", dest="dst_clocks")

    def validate_args_app_specific(self, args: Namespace) -> None:
        if args.do_auto_conf:
            raise NotImplementedError("Cannot handle PHC2SYS auto config yet")
        if args.pps_source is not None:
            raise NotImplementedError("Cannot handle PPS yet")

        if args.source_clock is None:
            raise ValueError("No source clock `-s` specified")

        self.clock_aliases = {}

        self.source_clock = get_canonicalized_clock(args.source_clock)
        self.clock_aliases[args.source_clock] = self.source_clock

        dst_clocks = args.dst_clocks or ["CLOCK_REALTIME"]

        self.dst_clocks = set()
        for clock in dst_clocks:
            canonicalized = get_canonicalized_clock(clock)
            self.clock_aliases[clock] = canonicalized
            self.dst_clocks.add(canonicalized)

    def override_app_specific(self, args: Namespace, config: ConfigParser) -> list[str]:
        return ["do_auto_conf", "source_clock", "dst_clocks", "pps_source"]


@dataclass
class Phc2SysRunningState(State):
    message_re = r"\[(?P<monotonic_time_s>[0-9]+\.[0-9]+)\]\s+(?P<message>.*)\s*$"
    offset_re = r"(?P<dst_clock>\w+)\s+(?P<src_clock_type>\w+)\s+offset\s+(?P<offset_ns>[+-]?\d+)\s+s(?P<servo_state>[0-3])\s+freq\s+(?P<freq_offset_ppb>[+-]?\d+)(?:\s+delay\s+(?P<delay_ns>[+-]?\d+))?"

    config: Phc2SysConfig
    dst_clock_states: dict[ClockId, SlaveClockState] = field(default_factory=dict)

    def _parse_offset(self, message: str):
        m = re.match(Phc2SysRunningState.offset_re, message)
        if not m:
            return False

        dst_clock = m["dst_clock"]
        offset_ns = int(m["offset_ns"])
        freq_offset_ppb = int(m["freq_offset_ppb"])
        servo_state = ServoState.ValueType(int(m["servo_state"]))
        delay_ns = int(m.groupdict().get("delay_ns", "0"))

        canonicalized = self.config.clock_aliases.get(dst_clock)
        if canonicalized is None:
            return False

        self.dst_clock_states[canonicalized] = SlaveClockState(
            servo_state=servo_state,
            offset_ns=offset_ns,
            delay_ns=delay_ns,
            frequency_offset_ppb=freq_offset_ppb,
        )
        return True

    def parse(self, entry: JournalEntry) -> Generator[Event, None, State]:
        if entry.message is None:
            return self

        m = re.match(Phc2SysRunningState.message_re, entry.message)
        if not m:
            return self

        message: str = m["message"]
        if self._parse_offset(message):
            return self
        return self
        yield  # force this function to be a generator
