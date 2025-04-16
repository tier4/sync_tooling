from networkx import DiGraph

from sync_graph.sync_graph import SyncGraph
from sync_tooling_msgs.clock_alias_update_pb2 import ClockAliasUpdate
from sync_tooling_msgs.clock_diff_measurement_pb2 import ClockDiffMeasurement
from sync_tooling_msgs.clock_id_pb2 import ClockId
from sync_tooling_msgs.clock_master_update_pb2 import ClockMasterUpdate
from sync_tooling_msgs.diag_tree import aggregate
from sync_tooling_msgs.diag_tree_pb2 import DiagTree
from sync_tooling_msgs.graph_update_pb2 import GraphUpdate
from sync_tooling_msgs.phc2sys_status_message_pb2 import Phc2SysStatusMessage
from sync_tooling_msgs.phc2sys_update_pb2 import Phc2SysUpdate
from sync_tooling_msgs.port_id_pb2 import PortId
from sync_tooling_msgs.port_state_pb2 import PortState
from sync_tooling_msgs.port_state_update_pb2 import PortStateUpdate
from sync_tooling_msgs.ptp4l_port_status_message_pb2 import Ptp4lPortStatusMessage
from sync_tooling_msgs.ptp4l_status_message_pb2 import Ptp4lStatusMessage
from sync_tooling_msgs.ptp_parent_update_pb2 import PtpParentUpdate
from sync_tooling_msgs.self_reported_clock_state_update_pb2 import (
    SelfReportedClockStateUpdate,
)
from sync_tooling_msgs.servo_state_pb2 import ServoState
from sync_tooling_msgs.slave_clock_state_pb2 import SlaveClockState


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
        SelfReportedClockStateUpdate: "self_reported_clock_state_update",
    }

    if type(u) in type_map:
        return GraphUpdate(**{type_map[type(u)]: u})
    raise KeyError()


def graph_after_updates(*updates: GraphUpdate, reference: DiGraph | None = None):
    g = SyncGraph(reference_graph=reference)
    for u in updates:
        g.update(u)
    return g


def make_phc2sys_link(src: ClockId, dst: ClockId, faulty: bool):
    link_state = (
        SlaveClockState(servo_state=ServoState.SERVO_UNLOCKED)
        if faulty
        else SlaveClockState(servo_state=ServoState.SERVO_LOCKED)
    )
    return _gu(Phc2SysUpdate(src=src, dst=dst, clock_state=link_state))


def make_ptp_link(src_port: PortId, dst: ClockId, faulty: bool):
    port_state = PortState.PS_FAULTY if faulty else PortState.PS_MASTER
    u_port_state = _gu(PortStateUpdate(port_id=src_port, port_state=port_state))
    u_parent = _gu(PtpParentUpdate(clock_id=dst, parent=src_port))
    return [u_port_state, u_parent]


def make_measurement(src: ClockId, dst: ClockId, faulty: bool):
    diff_ns = 1_000_000_000 if faulty else 0
    return _gu(ClockDiffMeasurement(src=src, dst=dst, diff_ns=diff_ns))


def make_master_link(src: ClockId, dst: ClockId, faulty: bool):
    offset_ns = 1_000_000_000 if faulty else 0
    return _gu(ClockMasterUpdate(clock_id=dst, master=src, master_offset_ns=offset_ns))


def aggregated_status_label(diag_tree: DiagTree):
    diag_status = aggregate(diag_tree)
    return diag_status.WhichOneof("status")
