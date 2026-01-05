"""Adapter for publishing sync graph diagnostics as ROS 2 diagnostic messages."""

import networkx as nx
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from rclpy.node import Node
from sync_graph.sync_graph import SyncGraph
from sync_tooling_msgs.clock_id import readable_clock_id
from sync_tooling_msgs.clock_id_pb2 import ClockId
from sync_tooling_msgs.diag_status_pb2 import DiagStatus
from sync_tooling_msgs.diag_tree import aggregate, flatten
from sync_tooling_msgs.diag_tree_pb2 import DiagTree
from sync_tooling_msgs.ok_pb2 import Ok


def _get_message(diag_status: DiagStatus | str) -> str:
    """Extract the message string from a diagnostic status."""
    if isinstance(diag_status, str):
        return diag_status

    match diag_status.WhichOneof("status"):
        case "error":
            status = diag_status.error
        case "warning":
            status = diag_status.warning
        case "ok":
            status = diag_status.ok
        case "unknown":
            status = diag_status.unknown
        case _:
            raise AssertionError()

    return status.msg


def _diag_status_to_ros_diag_status(diag_tree: DiagTree):
    """Convert a DiagTree to a ROS DiagnosticStatus message."""
    ros_status = DiagnosticStatus()

    default_status = DiagStatus(ok=Ok(msg="OK"))
    diag_status = aggregate(diag_tree, default_status)
    match diag_status.WhichOneof("status"):
        case "error":
            ros_status.level = DiagnosticStatus.ERROR
        case "warning" | "unknown":
            ros_status.level = DiagnosticStatus.WARN
        case "ok":
            ros_status.level = DiagnosticStatus.OK
        case _:
            raise AssertionError()

    ros_status.message = _get_message(diag_status)

    key_values = flatten(diag_tree)
    key_values = [
        KeyValue(key=k, value=_get_message(v) or "") for k, v in key_values.items()
    ]
    ros_status.values = key_values

    return ros_status


class Ros2DiagnosticsAdapter:
    """Publishes sync graph diagnostics to ROS 2 /diagnostics topic."""

    HARDWARE_ID = "SYNC.DIAG"

    def __init__(self, node: Node) -> None:
        """Initialize the adapter with a ROS 2 node."""
        self._node = node
        self._diag_publisher = node.create_publisher(
            DiagnosticArray, "/diagnostics", 10
        )

    def diagnose(self, sg: SyncGraph):
        """Run diagnostics on the sync graph and publish results."""
        try:
            diag = self._diagnose_all(sg)
            self._diag_publisher.publish(diag)
        except Exception as e:  # noqa: BLE001
            print(e)

    def _diagnose_all(self, sg: SyncGraph) -> DiagnosticArray:
        """Build a complete DiagnosticArray from the sync graph."""
        arr = DiagnosticArray()
        arr.header.stamp = self._node.get_clock().now().to_msg()

        arr.status = []
        arr.status += self._diagnose_graph(sg)
        arr.status += self._diagnose_reference(sg)
        arr.status += self._diagnose_clocks(sg)

        return arr

    def _diagnose_graph(self, sg: SyncGraph):
        """Diagnose overall graph health."""
        diag_tree = sg.diagnose_graph()
        ros_status = _diag_status_to_ros_diag_status(diag_tree)
        ros_status.name = "Graph health"
        ros_status.hardware_id = Ros2DiagnosticsAdapter.HARDWARE_ID
        return [ros_status]

    def _diagnose_reference(self, sg: SyncGraph):
        """Diagnose reference graph adherence."""
        diag_tree = sg.diagnose_reference_adherence()
        ros_status = _diag_status_to_ros_diag_status(diag_tree)
        ros_status.name = "Graph reference adherence"
        ros_status.hardware_id = Ros2DiagnosticsAdapter.HARDWARE_ID
        return [ros_status]

    def _diagnose_clocks(self, sg: SyncGraph) -> list[DiagnosticStatus]:
        """Diagnose each clock in the reference graph."""
        if sg.reference_graph is None:
            return []

        clocks = nx.lexicographical_topological_sort(
            sg.reference_graph, key=readable_clock_id
        )
        return [self._diagnose_clock(sg, clock_id) for clock_id in clocks]

    def _diagnose_clock(self, sg: SyncGraph, clock_id: ClockId):
        """Diagnose a single clock."""
        canonical_id = sg.get_canonical_clock_id(clock_id)

        if canonical_id in sg._graph:
            diag_tree = sg.diagnose_clock(canonical_id)
            ros_status = _diag_status_to_ros_diag_status(diag_tree)
        else:
            ros_status = DiagnosticStatus()
            ros_status.level = DiagnosticStatus.ERROR
            ros_status.message = "Clock not present"

        ros_status.hardware_id = Ros2DiagnosticsAdapter.HARDWARE_ID
        # Even if the canonical ID might be different, output diagnostics using the clock ID as
        # provided in the reference graph for easier understandability
        ros_status.name = readable_clock_id(clock_id)

        return ros_status
