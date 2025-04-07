from dataclasses import dataclass, field

from pmc_monitor.pmc_protocol import (
    CurrentDataSet,
    DefaultDataSet,
    ParentDataSet,
    PortDataSet,
)


class Unsupported:
    pass


@dataclass
class PtpPort:
    """
    The current state of a PTP port as reported by PMC.
    """

    port_ds: PortDataSet

    def id(self):
        return self.port_ds.portIdentity


@dataclass
class PtpInstance:
    """
    The current state of a PTP instance as reported by PMC.
    """

    # Whether this instance is the PTP instance that PMC is running on
    is_local_instance: bool

    # The clock identity of this PTP instance, e.g. `000000.fffe.000000`
    identity: str

    default_ds: DefaultDataSet | None = None
    current_ds: CurrentDataSet | Unsupported | None = None
    parent_ds: ParentDataSet | Unsupported | None = None
    ports: dict[int, PtpPort] = field(default_factory=dict)

    def id(self):
        return self.identity
