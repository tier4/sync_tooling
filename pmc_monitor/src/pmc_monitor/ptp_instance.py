from dataclasses import dataclass, field

from diag_tree import Diagnosable, Unknown
from pmc_monitor.pmc_protocol import (
    CurrentDataSet,
    DefaultDataSet,
    ParentDataSet,
    PortDataSet,
    PortStatsNp,
    TimePropertiesDataSet,
    TimeStatusNp,
)
from sync_tooling_msgs.diag_status_pb2 import DiagStatus
from sync_tooling_msgs.diag_tree_pb2 import DiagTree


@dataclass
class Unsupported(Diagnosable):
    def diagnose(self):
        return DiagTree(
            status=DiagStatus(
                unknown=Unknown(msg="PTP instance does not support this command")
            )
        )


@dataclass
class PtpPort:
    port_ds: PortDataSet
    port_stats: PortStatsNp | Unsupported | None = None

    def id(self):
        return self.port_ds.portIdentity


@dataclass
class PtpInstance:
    is_local_instance: bool
    default_ds: DefaultDataSet
    current_ds: CurrentDataSet | Unsupported | None = None
    parent_ds: ParentDataSet | Unsupported | None = None
    time_status_ds: TimeStatusNp | Unsupported | None = None
    time_properties_ds: TimePropertiesDataSet | Unsupported | None = None
    ports: dict[int, PtpPort] = field(default_factory=dict)

    def id(self):
        return self.default_ds.clockIdentity
