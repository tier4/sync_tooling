import socket
from argparse import REMAINDER, ArgumentParser
from collections import namedtuple
from datetime import timedelta

import rclpy
import yaml
from networkx import DiGraph

from diag_master.ros2_diagnostics_adapter import Ros2DiagnosticsAdapter
from diag_master.web_ui import WebUi
from ros2_transport.server import Ros2Server
from sync_graph.sync_graph import SyncGraph
from sync_graph.timed_graph_update_queue import TimedGraphUpdateQueue
from sync_graph.yaml import clock_tree_to_digraph
from sync_tooling_msgs.graph_update_pb2 import GraphUpdate

Args = namedtuple("Args", ["topic", "reference", "ros_args", "update_expiry_s"])


class DiagMaster:
    def __init__(
        self,
        topic: str,
        reference_graph: DiGraph | None,
        update_expiry: timedelta,
        enable_ros2_diagnostics: bool,
        enable_web_ui: bool,
    ) -> None:
        hostname = socket.gethostname()
        self._node = rclpy.create_node(hostname, namespace="/sync_diag/master")  # type: ignore
        self._ros2_server = Ros2Server(topic, self._node, self.on_graph_update)
        self._reference_graph = reference_graph
        self._update_queue = TimedGraphUpdateQueue(update_expiry)

        self._diagnostic_timer = self._node.create_timer(1, self.on_diagnostic_timer)

        if enable_ros2_diagnostics:
            self._diagnostics_adapter = Ros2DiagnosticsAdapter(self._node)

        if enable_web_ui:
            self._web_ui = WebUi()
            self._web_ui.run()

    def on_graph_update(self, u: GraphUpdate):
        self._update_queue.push(u)

    def on_diagnostic_timer(self):
        sg = self.sync_graph

        if self._diagnostics_adapter:
            self._diagnostics_adapter.diagnose(sg)

        if self._web_ui:
            self._web_ui.update(sg)

    @property
    def sync_graph(self):
        sg = SyncGraph(self._reference_graph)
        for u in self._update_queue.updates:
            sg.update(u)
        return sg


def parse_args() -> Args:
    parser = ArgumentParser()
    parser.add_argument("--topic", "-t", default="/sync_diag/graph_updates")
    parser.add_argument(
        "--update-expiry-s",
        "-e",
        type=int,
        default=2,
        help="After how many seconds a received graph update is removed from the graph.",
    )
    parser.add_argument("--instrument", action="store_true")
    parser.add_argument(
        "--reference", "-r", help="Reference synchronization graph in YAML format."
    )
    parser.add_argument(
        "--ros-args",
        nargs=REMAINDER,
        help="Arguments passed along to ROS 2. See https://docs.ros.org/en/rolling/How-To-Guides/Node-arguments.html for details.",
    )
    return parser.parse_args()  # type: ignore


def parse_reference_graph(reference_path: str):
    with open(reference_path) as f:
        yaml_data = yaml.safe_load(f)

    return clock_tree_to_digraph(yaml_data["clock_tree"])


def initialize_master(args: Args):
    reference_graph = parse_reference_graph(args.reference) if args.reference else None
    update_expiry = timedelta(seconds=args.update_expiry_s)

    diag_master = DiagMaster(args.topic, reference_graph, update_expiry, True, True)
    return diag_master


def main():
    args = parse_args()
    rclpy.init(args=args.ros_args)
    diag_master = initialize_master(args)
    rclpy.spin(diag_master._node)
    rclpy.shutdown()
