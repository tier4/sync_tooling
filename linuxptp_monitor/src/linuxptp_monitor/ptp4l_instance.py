from abc import ABCMeta
from argparse import ArgumentParser, Namespace
from configparser import ConfigParser
from dataclasses import dataclass, field
from enum import Enum, EnumMeta
import re
from typing import Dict, Literal

from diag_tree import DiagTree, Diagnosable, Ok, Warning, Error
from journal_monitor.journal_monitor import JournalEntry
from linuxptp_monitor.ethtool_harness import CanonicalizedClock, get_canonicalized_clock
from linuxptp_monitor.linuxptp_config import LinuxPtpConfig
from linuxptp_monitor.state_machine import State


class DiagnosableEnumMeta(EnumMeta, ABCMeta):
    pass


# Adapted from fsm.h of LinuxPTP
class PortState(Enum, Diagnosable, metaclass=DiagnosableEnumMeta):
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

    def diagnose(self) -> DiagTree:
        match self:
            case PortState.MASTER | PortState.SLAVE | PortState.GRAND_MASTER:
                return Ok(f"Port is operating nominally ({self.name})")
            case (
                PortState.LISTENING
                | PortState.INITIALIZING
                | PortState.PRE_MASTER
                | PortState.UNCALIBRATED
            ):
                return Warning(f"Port is in a transient state ({self.name})")
            case PortState.DISABLED | PortState.DISABLED:
                return Warning(f"Port is not being used ({self.name})")
            case _:
                return Error(f"Port is not working correctly ({self.name})")


class SyncState(Enum, Diagnosable, metaclass=DiagnosableEnumMeta):
    SERVO_UNLOCKED = 0
    SERVO_JUMP = 1
    SERVO_LOCKED = 2
    SERVO_LOCKED_STABLE = 3

    def diagnose(self) -> DiagTree:
        match self:
            case SyncState.SERVO_LOCKED | SyncState.SERVO_LOCKED_STABLE:
                return Ok(f"Locked ({self.name})")
            case _:
                return Error(f"Not locked ({self.name})")


class NetworkTransport(Enum):
    UDP_IPV4 = 1
    UDP_IPV6 = 2
    IEEE_802_3 = 3

    @classmethod
    def from_flag(cls, flag: Literal["-2", "-4", "-6"]):
        match flag:
            case "-2":
                return NetworkTransport.IEEE_802_3
            case "-4":
                return NetworkTransport.UDP_IPV4
            case "-6":
                return NetworkTransport.UDP_IPV6

    @classmethod
    def from_label(cls, label: str):
        match label:
            case "L2":
                return NetworkTransport.IEEE_802_3
            case "UDPv4":
                return NetworkTransport.UDP_IPV4
            case "UDPv6":
                return NetworkTransport.UDP_IPV6
            case other:
                raise ValueError(
                    f"Value '{other}' is not recognized as a valid network transport"
                )

    def to_flag(self):
        match self:
            case NetworkTransport.IEEE_802_3:
                return "-2"
            case NetworkTransport.UDP_IPV4:
                return "-4"
            case NetworkTransport.UDP_IPV6:
                return "-6"


@dataclass(init=False)
class Ptp4lConfig(LinuxPtpConfig):
    clock: CanonicalizedClock
    uds_address: str
    network_transport: NetworkTransport
    ports: list[str]

    def add_args_app_specific(self, parser: ArgumentParser) -> None:
        parser.add_argument("-i", action="append", dest="ports")
        parser.add_argument("-p", metavar="phc-device", dest="phc_device")
        parser.add_argument(
            "-2", action="store_const", const=NetworkTransport.from_flag("-2")
        )
        parser.add_argument(
            "-4", action="store_const", const=NetworkTransport.from_flag("-4")
        )
        parser.add_argument(
            "-6", action="store_const", const=NetworkTransport.from_flag("-6")
        )
        parser.add_argument(
            "-S", action="store_const", const="software", dest="time_stamping"
        )
        parser.add_argument(
            "-H", action="store_const", const="hardware", dest="time_stamping"
        )
        parser.add_argument(
            "-L", action="store_const", const="legacy", dest="time_stamping"
        )
        parser.add_argument("--uds_address")

    def validate_args_app_specific(self, args: Namespace) -> None:
        if args.phc_device is not None:
            raise NotImplementedError("Cannot handle deprecated `-p` option")

    def override_app_specific(self, args: Namespace, config: ConfigParser) -> list[str]:
        for port in args.ports:
            if port not in config.sections():
                config.add_section(port)

        return ["ports", "phc_device", "legacy_timestamping"]

    def validate_config_app_specific(self, config: ConfigParser) -> None:
        ports = [section for section in config.sections() if section != "global"]

        time_stamping = config["global"]["time_stamping"]
        match time_stamping:
            case "software":
                clocks = ["CLOCK_REALTIME"]
            case "hardware":
                clocks = ports
            case other:
                raise NotImplementedError(f"Cannot handle `time_stamping = {other}`")

        clocks = {get_canonicalized_clock(clock) for clock in clocks}
        if len(clocks) != 1:
            raise RuntimeError(
                f"PTP4L instance has to be using just one clock, is using multiple ({', '.join(map(str, clocks))})"
            )

        self.clock = next(iter(clocks))  # type: ignore
        self.uds_address = config["global"]["uds_address"]
        self.network_transport = NetworkTransport.from_label(
            config["global"]["network_transport"]
        )
        self.ports = ports


@dataclass
class Ptp4lRunningState(State):
    message_re = r"\[(?P<monotonic_time_s>[0-9]+\.[0-9]+)\]\s+(?P<message>.*)\s*$"
    port_re = r"port\s+(?P<port_id>[0-9]+):\s+(?P<port_message>.*)\s*$"
    state_change_re = (
        r"(?P<from_state>\w+)\s+to\s+(?P<to_state>\w+)\s+on\s+(?P<event>\w+)\s*$"
    )
    master_offset_re = r"master offset (?P<offset_ns>[+-]?\d+)\s+s(?P<sync_state>[0-3])\s+freq\s+(?P<freq_offset_ppb>[+-]?\d+)\s+path delay\s+(?P<path_delay_ns>[+-]?\d+)"

    config: Ptp4lConfig
    port_states: Dict[int, PortState] = field(default_factory=dict)

    def _parse_port_state_change(self, message: str):
        m = re.match(Ptp4lRunningState.port_re, message)
        if not m:
            return False
        port_id = int(m["port_id"])
        port_message = m["port_message"]

        m = re.match(Ptp4lRunningState.state_change_re, port_message)
        if not m:
            return True

        from_state = m["from_state"]
        to_state = m["to_state"]
        event = m["event"]

        print(f"Port {port_id} changed from {from_state} to {to_state} on {event}")
        self.port_states[port_id] = PortState[to_state]

        return True

    def _parse_master_offset(self, message: str):
        m = re.match(Ptp4lRunningState.master_offset_re, message)
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
        if entry.message is None:
            return self

        m = re.match(Ptp4lRunningState.message_re, entry.message)
        if not m:
            return self

        message: str = m["message"]
        if self._parse_master_offset(message):
            return self
        if self._parse_port_state_change(message):
            return self

        return self
