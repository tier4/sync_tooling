from typing import Literal

from sync_graph.sync_graph import SyncGraph
from sync_tooling_msgs.clock_alias_update_pb2 import ClockAliasUpdate
from sync_tooling_msgs.clock_diff_measurement_pb2 import ClockDiffMeasurement
from sync_tooling_msgs.clock_master_update_pb2 import ClockMasterUpdate
from sync_tooling_msgs.diag_tree import aggregate
from sync_tooling_msgs.diag_tree_pb2 import DiagTree
from sync_tooling_msgs.graph_update_pb2 import GraphUpdate
from sync_tooling_msgs.phc2sys_status_message_pb2 import Phc2SysStatusMessage
from sync_tooling_msgs.phc2sys_update_pb2 import Phc2SysUpdate
from sync_tooling_msgs.port_state_update_pb2 import PortStateUpdate
from sync_tooling_msgs.ptp4l_port_status_message_pb2 import Ptp4lPortStatusMessage
from sync_tooling_msgs.ptp4l_status_message_pb2 import Ptp4lStatusMessage
from sync_tooling_msgs.ptp_parent_update_pb2 import PtpParentUpdate


def _gu(u):
    """Cast an arbitrary graph update item to the `GraphUpdate` proto"""
    type_map = {
        ClockAliasUpdate: "clock_alias_update",
        ClockDiffMeasurement: "clock_diff_measurement",
        ClockMasterUpdate: "clock_master_update",
        Phc2SysUpdate: "phc2sys_update",
        PtpParentUpdate: "ptp_parent_update",
        PortStateUpdate: "port_state_update",
        Ptp4lPortStatusMessage: "ptp4l_port_status_msg",
        Ptp4lStatusMessage: "ptp4l_status_msg",
        Phc2SysStatusMessage: "phc2sys_status_msg",
    }

    if type(u) in type_map:
        return GraphUpdate(**{type_map[type(u)]: u})
    raise KeyError()


def graph_after_updates(*updates: GraphUpdate):
    g = SyncGraph()
    for u in updates:
        g.update(u)
    return g


def assert_aggregated_status(
    diag_tree: DiagTree, status: Literal["ok", "warning", "error", "unknown", None]
):
    diag_status = aggregate(diag_tree)
    assert (
        diag_status.WhichOneof("status") == status
    ), f"Expected {status}, got {diag_status.WhichOneof('status')}"
