import signal
import socket
import sys
from argparse import REMAINDER, ArgumentParser
from collections import namedtuple
from datetime import timedelta
from typing import Callable

import rclpy
import yaml

from diag_master.ros2_diagnostics_adapter import Ros2DiagnosticsAdapter
from diag_master.web_ui import WebUi
from linuxptp_monitor.util import hostname_to_node_name
from ros2_transport.server import Ros2Server
from sync_graph.sync_graph import SyncGraph
from sync_graph.timed_graph_update_queue import TimedGraphUpdateQueue
from sync_graph.update_aggregator import aggregate_clock_diff_measurements
from sync_graph.yaml import to_sync_graph_args
from sync_tooling_msgs.graph_update_pb2 import GraphUpdate

Args = namedtuple(
    "Args",
    [
        "topic",
        "config_files",
        "ros_args",
        "update_expiry_s",
        "enable_web_ui",
    ],
)


class DiagMaster:
    def __init__(
        self,
        topic: str,
        sync_graph_factory: Callable[[], SyncGraph],
        update_expiry: timedelta,
        enable_ros2_diagnostics: bool,
        enable_web_ui: bool,
    ) -> None:
        hostname = socket.gethostname()

        node_name = hostname_to_node_name(hostname)
        self._node = rclpy.create_node(node_name, namespace="/sync_diag/master")  # type: ignore
        self._ros2_server = Ros2Server(topic, self._node, self.on_graph_update)
        self._sync_graph_factory = sync_graph_factory
        self._update_queue = TimedGraphUpdateQueue(update_expiry)

        self._diagnostic_timer = self._node.create_timer(1, self.on_diagnostic_timer)

        if enable_ros2_diagnostics:
            self._diagnostics_adapter = Ros2DiagnosticsAdapter(self._node)
        else:
            self._diagnostics_adapter = None

        if enable_web_ui:
            self._web_ui = WebUi()
            self._web_ui.run()
        else:
            self._web_ui = None

    def on_graph_update(self, u: GraphUpdate):
        self._update_queue.push(u)

    def on_diagnostic_timer(self):
        sg = self.sync_graph

        if self._diagnostics_adapter:
            self._diagnostics_adapter.diagnose(sg)

        if self._web_ui:
            self._web_ui.update(sg)

    def shutdown(self):
        self._diagnostic_timer.cancel()
        self._node.destroy_node()

    @property
    def sync_graph(self):
        sg = self._sync_graph_factory()
        updates = self._update_queue.updates
        aggregated_updates = aggregate_clock_diff_measurements(updates)
        for u in aggregated_updates:
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
        "--config-files",
        "-f",
        nargs="+",
        help="Configuration such as reference graph and measurement thresholds in YAML format. "
        "If multiple files are given, they are merged. For keys that appear in multiple files, "
        "the last file takes precedence.",
    )
    parser.add_argument(
        "--web-ui", action="store_true", dest="enable_web_ui", default=False
    )
    parser.add_argument(
        "--ros-args",
        nargs=REMAINDER,
        help="Arguments passed along to ROS 2. See https://docs.ros.org/en/rolling/How-To-Guides/Node-arguments.html for details.",
    )
    return parser.parse_args()  # type: ignore


def read_configs_raw(config_paths: list[str]):
    merged_config = {}

    for config_path in config_paths:
        with open(config_path) as f:
            yaml_data = yaml.safe_load(f)

            # This does not recursively merge the data, but adds or overwrites the top-level
            # entries in the order they are given.
            merged_config.update(yaml_data)

    return merged_config


def initialize_master(args: Args):
    config_raw = read_configs_raw(args.config_files)
    if not config_raw:
        print(
            "At least one config file must be given. (Use -f to specify config files.)",
            file=sys.stderr,
        )
        exit(1)

    config, reference_graph = to_sync_graph_args(config_raw)

    def sync_graph_factory():
        return SyncGraph(config, reference_graph)

    update_expiry = timedelta(seconds=args.update_expiry_s)

    diag_master = DiagMaster(
        args.topic,
        sync_graph_factory,
        update_expiry,
        True,
        args.enable_web_ui,
    )
    return diag_master


def main():
    args = parse_args()
    rclpy.init(args=args.ros_args)
    diag_master = initialize_master(args)

    def shutdown(signum, frame):
        print(f"Shutting down DiagMaster on {signal.Signals(signum).name}...")
        diag_master.shutdown()
        rclpy.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    rclpy.spin(diag_master._node)
    rclpy.shutdown()
