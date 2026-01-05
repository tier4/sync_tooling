"""PTP4L configuration and state parsing."""

import re
from argparse import ArgumentParser, Namespace
from configparser import ConfigParser
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Literal

from journal_monitor.journal_monitor import JournalEntry
from sync_tooling_msgs.clock_id_pb2 import ClockId
from sync_tooling_msgs.error_pb2 import Error
from sync_tooling_msgs.graph_update_pb2 import GraphUpdate
from sync_tooling_msgs.port_id_pb2 import PortId
from sync_tooling_msgs.port_state import port_state_value
from sync_tooling_msgs.port_state_pb2 import PortState
from sync_tooling_msgs.ptp4l_port_status_message_pb2 import Ptp4lPortStatusMessage
from sync_tooling_msgs.ptp4l_status_message_pb2 import Ptp4lStatusMessage
from sync_tooling_msgs.servo_state_pb2 import ServoState
from sync_tooling_msgs.slave_clock_state_pb2 import SlaveClockState
from sync_tooling_msgs.warning_pb2 import Warning

from linuxptp_monitor.ethtool_harness import get_canonicalized_clock
from linuxptp_monitor.linuxptp_config import LinuxPtpConfig
from linuxptp_monitor.state_machine import State


class NetworkTransport(Enum):
    """PTP network transport type."""

    UDP_IPV4 = 1
    UDP_IPV6 = 2
    IEEE_802_3 = 3

    @classmethod
    def from_flag(cls, flag: Literal["-2", "-4", "-6"]):
        """Create from ptp4l command-line flag."""
        match flag:
            case "-2":
                return NetworkTransport.IEEE_802_3
            case "-4":
                return NetworkTransport.UDP_IPV4
            case "-6":
                return NetworkTransport.UDP_IPV6

    @classmethod
    def from_label(cls, label: str):
        """Create from config file label (L2, UDPv4, UDPv6)."""
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
        """Convert to ptp4l command-line flag."""
        match self:
            case NetworkTransport.IEEE_802_3:
                return "-2"
            case NetworkTransport.UDP_IPV4:
                return "-4"
            case NetworkTransport.UDP_IPV6:
                return "-6"


@dataclass(init=False)
class Ptp4lConfig(LinuxPtpConfig):
    """Configuration for a ptp4l instance.

    Attributes:
        clock: The clock used by this ptp4l instance.
        uds_address: Unix domain socket address for PMC.
        network_transport: The network transport type.
        ports: List of network interface names.

    """

    clock: ClockId
    uds_address: str
    network_transport: NetworkTransport
    ports: list[str]

    def add_args_app_specific(self, parser: ArgumentParser) -> None:
        """Add ptp4l-specific arguments to the parser."""
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
        parser.add_argument("--domainNumber", type=int)

    def validate_args_app_specific(self, args: Namespace) -> None:
        """Validate ptp4l-specific arguments."""
        if args.phc_device is not None:
            raise NotImplementedError("Cannot handle deprecated `-p` option")

    def override_app_specific(self, args: Namespace, config: ConfigParser) -> list[str]:
        """Return list of args that override config file settings."""
        for port in args.ports:
            if port not in config.sections():
                config.add_section(port)

        return ["ports", "phc_device", "legacy_timestamping"]

    def validate_config_app_specific(self, config: ConfigParser) -> None:
        """Validate ptp4l-specific configuration."""
        ports = [section for section in config.sections() if section != "global"]

        time_stamping = config["global"]["time_stamping"]
        match time_stamping:
            case "software":
                clocks = ["CLOCK_REALTIME"]
            case "hardware":
                clocks = ports
            case other:
                raise NotImplementedError(f"Cannot handle `time_stamping = {other}`")

        clocks = {get_canonicalized_clock(clock) for clock in clocks}  # type: ignore
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
        self.transport_specific = int(
            config["global"].get("transportSpecific", "0"), base=0
        )
        self.domain = int(config["global"].get("domainNumber", "0"), base=0)


@dataclass
class Ptp4lRunningState(State):
    """Running state for ptp4l log parsing.

    Attributes:
        config: The ptp4l configuration.
        port_states: Current state of each port by port number.
        slave_clock_state: Current slave clock state, if available.

    """

    message_re = r"\[(?P<monotonic_time_s>[0-9]+\.[0-9]+)\]\s+(?P<message>.*)\s*$"
    port_re = r"port\s+(?P<port_id>[0-9]+):\s+(?P<port_message>.*)\s*$"
    state_change_re = (
        r"(?P<from_state>\w+)\s+to\s+(?P<to_state>\w+)\s+on\s+(?P<event>\w+)\s*$"
    )
    master_offset_re = r"master offset (?P<offset_ns>[+-]?\d+)\s+s(?P<servo_state>[0-3])\s+freq\s+(?P<freq_offset_ppb>[+-]?\d+)\s+path delay\s+(?P<path_delay_ns>[+-]?\d+)"

    config: Ptp4lConfig
    port_states: Dict[int, PortState.ValueType] = field(default_factory=dict)
    slave_clock_state: SlaveClockState | None = None

    def _parse_port_state_change(self, message: str):
        m = re.match(Ptp4lRunningState.port_re, message)
        if not m:
            return False
        port_id = int(m["port_id"])
        port_message = m["port_message"]

        m = re.match(Ptp4lRunningState.state_change_re, port_message)
        if not m:
            return True

        to_state = m["to_state"]
        self.port_states[port_id] = port_state_value(to_state)
        return True

    def _parse_master_offset(self, message: str):
        m = re.match(Ptp4lRunningState.master_offset_re, message)
        if not m:
            return False

        offset_ns = int(m["offset_ns"])
        freq_offset_ppb = int(m["freq_offset_ppb"])
        servo_state = ServoState.ValueType(int(m["servo_state"]))
        delay_ns = int(m["path_delay_ns"])

        self.slave_clock_state = SlaveClockState(
            servo_state=servo_state,
            offset_ns=offset_ns,
            delay_ns=delay_ns,
            frequency_offset_ppb=freq_offset_ppb,
        )
        return True

    def _parse_non_nominal_status_message(
        self, priority: JournalEntry.Priority, message: str
    ):
        if priority == JournalEntry.Priority.Warning:
            status = {"warning": Warning(msg=message)}
        else:
            status = {"error": Error(msg=message)}
        m = re.match(Ptp4lRunningState.port_re, message)
        if not m:
            return GraphUpdate(
                ptp4l_status_msg=Ptp4lStatusMessage(
                    clock_id=self.config.clock,
                    **status,  # type: ignore
                )
            )  # type: ignore
        port_id = PortId(
            clock_id=self.config.clock,
            port_number=int(m["port_id"]),
            ptp_domain=self.config.domain,
        )
        return GraphUpdate(
            ptp4l_port_status_msg=Ptp4lPortStatusMessage(port_id=port_id, **status)  # type: ignore
        )  # type: ignore

    def parse(self, entry: JournalEntry):
        """Parse a journal entry and yield graph update events."""
        if entry.message is None:
            return self

        if (
            entry.priority is not None
            and entry.priority.value <= JournalEntry.Priority.Warning.value
        ):
            event = self._parse_non_nominal_status_message(
                entry.priority, entry.message
            )
            yield event
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
