"""PTP instance and port state classes."""

from dataclasses import dataclass, field

from pmc_monitor.pmc_protocol import (
    CurrentDataSet,
    DefaultDataSet,
    ParentDataSet,
    PortDataSet,
)


class Unsupported:
    """Marker class for unsupported datasets."""


@dataclass
class PtpPort:
    """The current state of a PTP port as reported by PMC.

    Attributes:
        port_ds: The port dataset from PMC.

    """

    port_ds: PortDataSet

    def id(self):
        """Return the port identity."""
        return self.port_ds.portIdentity


@dataclass
class PtpInstance:
    """The current state of a PTP instance as reported by PMC.

    Attributes:
        is_local_instance: Whether this is the PTP instance that PMC is running on.
        identity: The clock identity (e.g., '123456.fffe.111111').
        default_ds: The default dataset, if available.
        current_ds: The current dataset, if available.
        parent_ds: The parent dataset, if available.
        ports: Map of port number to PtpPort.

    """

    is_local_instance: bool
    identity: str

    default_ds: DefaultDataSet | None = None
    current_ds: CurrentDataSet | Unsupported | None = None
    parent_ds: ParentDataSet | Unsupported | None = None
    ports: dict[int, PtpPort] = field(default_factory=dict)

    def id(self):
        """Return the clock identity."""
        return self.identity
