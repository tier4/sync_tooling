import threading
from typing import Callable

import networkx as nx
import rclpy
import rclpy.context
import rclpy.signals
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue

from sync_graph.sync_graph import SyncGraph
from sync_tooling_msgs.clock_id import readable_clock_id
from sync_tooling_msgs.clock_id_pb2 import ClockId
from sync_tooling_msgs.diag_status_pb2 import DiagStatus
from sync_tooling_msgs.diag_tree import aggregate, flatten
from sync_tooling_msgs.diag_tree_pb2 import DiagTree


def get_message(diag_status: DiagStatus) -> str | None:
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


def diag_status_to_ros_diag_status(diag_tree: DiagTree):
    ros_status = DiagnosticStatus()

    diag_status = aggregate(diag_tree)
    match diag_status.WhichOneof("status"):
        case "error":
            ros_status.level = DiagnosticStatus.ERROR
        case "warning" | "unknown":
            ros_status.level = DiagnosticStatus.WARN
        case "ok":
            ros_status.level = DiagnosticStatus.OK
        case _:
            raise AssertionError()

    ros_status.message = get_message(diag_status)

    key_values = flatten(diag_tree)
    key_values = [
        KeyValue(key=k, value=get_message(v) or "") for k, v in key_values.items()
    ]
    ros_status.values = key_values

    return ros_status


class Ros2Adapter:
    HARDWARE_ID = "SYNC.DIAG"

    def __init__(
        self, get_sync_graph: Callable[[], SyncGraph], ros_args: list[str]
    ) -> None:
        self.get_sync_graph = get_sync_graph

        rclpy.init(args=ros_args, signal_handler_options=rclpy.SignalHandlerOptions.NO)
        self.node = rclpy.create_node("sync_diag_master")  # type: ignore
        self.diag_publisher = self.node.create_publisher(
            DiagnosticArray, "/diagnostics", 10
        )

        self.node.create_timer(1, self.on_diagnostic_timer)
        self.ros_thread = threading.Thread(target=lambda: rclpy.spin(self.node))
        self.ros_thread.start()

    def on_diagnostic_timer(self):
        try:
            sg = self.get_sync_graph()
            diag = self.diagnose_all(sg)
            self.diag_publisher.publish(diag)
        except Exception as e:  # noqa: BLE001
            print(e)

    def diagnose_all(self, sg: SyncGraph) -> DiagnosticArray:
        arr = DiagnosticArray()
        arr.header.stamp = self.node.get_clock().now().to_msg()

        arr.status = []
        arr.status += self.diagnose_graph(sg)
        arr.status += self.diagnose_reference(sg)
        arr.status += self.diagnose_clocks(sg)

        return arr

    def _diagnose_clock(self, sg: SyncGraph, clock_id: ClockId):
        canonical_id = sg.get_canonical_clock_id(clock_id)

        if canonical_id in sg._graph:
            diag_tree = sg.diagnose_clock(canonical_id)
            ros_status = diag_status_to_ros_diag_status(diag_tree)
        else:
            ros_status = DiagnosticStatus()
            ros_status.level = DiagnosticStatus.ERROR
            ros_status.message = "Clock not present"

        ros_status.hardware_id = Ros2Adapter.HARDWARE_ID
        # Even if the canonical ID might be different, output diagnostics using the clock ID as
        # provided in the reference graph for easier understandability
        ros_status.name = readable_clock_id(clock_id)

        return ros_status

    def diagnose_clocks(self, sg: SyncGraph) -> list[DiagnosticStatus]:
        if sg.reference_graph is None:
            return []

        clocks = nx.lexicographical_topological_sort(
            sg.reference_graph, key=readable_clock_id
        )
        return [self._diagnose_clock(sg, clock_id) for clock_id in clocks]

    def diagnose_graph(self, sg: SyncGraph):
        diag_tree = sg.diagnose_graph()
        ros_status = diag_status_to_ros_diag_status(diag_tree)
        ros_status.name = "Graph health"
        ros_status.hardware_id = Ros2Adapter.HARDWARE_ID
        return [ros_status]

    def diagnose_reference(self, sg: SyncGraph):
        diag_tree = sg.diagnose_reference_adherence()
        ros_status = diag_status_to_ros_diag_status(diag_tree)
        ros_status.name = "Graph reference adherence"
        ros_status.hardware_id = Ros2Adapter.HARDWARE_ID
        return [ros_status]
