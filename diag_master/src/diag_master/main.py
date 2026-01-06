# Copyright 2025 TIER IV, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Diagnostic master entry point and main class."""

import signal
import socket
import sys
from argparse import REMAINDER, ArgumentParser
from collections import namedtuple
from datetime import timedelta
from typing import Callable

import rclpy
import yaml
from linuxptp_monitor.util import hostname_to_node_name
from ros2_transport.server import Ros2Server
from sync_graph.sync_graph import SyncGraph
from sync_graph.timed_graph_update_queue import TimedGraphUpdateQueue
from sync_graph.update_aggregator import aggregate_clock_diff_measurements
from sync_graph.yaml import to_sync_graph_args
from sync_tooling_msgs.graph_update_pb2 import GraphUpdate

from diag_master.ros2_diagnostics_adapter import Ros2DiagnosticsAdapter
from diag_master.web_ui import WebUi

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
    """Diagnostic master providing a web UI and ROS 2 diagnostics.

    The master subscribes to graph updates on a given ROS 2 topic, builds a synchronization graph
    from the received updates, and provides diagnostics via ROS 2 and a web UI.
    """

    def __init__(
        self,
        topic: str,
        sync_graph_factory: Callable[[], SyncGraph],
        update_expiry: timedelta,
        enable_ros2_diagnostics: bool,
        enable_web_ui: bool,
    ) -> None:
        """Initialize the diagnostic master.

        To guarantee stable performance in the presence of network or scheduling delays, graph
        updates are accumulated over a short time window (given by `update_expiry`), and merged
        to build a synchronization graph. Newer updates overwrite older ones for the same entities.
        Any updates received earlier than `update_expiry` are automatically dropped.

        Args:
            topic: ROS 2 topic to subscribe to for graph updates.
            sync_graph_factory: Factory function to create SyncGraph instances.
            update_expiry: How long to keep updates before expiring them.
            enable_ros2_diagnostics: Whether to publish ROS 2 diagnostics.
            enable_web_ui: Whether to start the web UI server.

        """
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
        """Handle an incoming graph update."""
        self._update_queue.push(u)

    def on_diagnostic_timer(self):
        """Periodic callback to run diagnostics, update the web UI and publish ROS 2 diagnostics."""
        sg = self.sync_graph

        if self._diagnostics_adapter:
            self._diagnostics_adapter.diagnose(sg)

        if self._web_ui:
            self._web_ui.update(sg)

    def shutdown(self):
        """Clean up resources and shut down the node."""
        self._diagnostic_timer.cancel()
        self._node.destroy_node()

    @property
    def sync_graph(self):
        """Build and return the current sync graph from queued updates."""
        sg = self._sync_graph_factory()
        updates = self._update_queue.updates
        aggregated_updates = aggregate_clock_diff_measurements(updates)
        for u in aggregated_updates:
            sg.update(u)
        return sg


def parse_args() -> Args:
    """Parse command-line arguments."""
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
    """Read and merge multiple YAML config files.

    Later files take precedence over earlier ones.
    """
    merged_config = {}

    for config_path in config_paths:
        with open(config_path) as f:
            yaml_data = yaml.safe_load(f)

            # This does not recursively merge the data, but adds or overwrites the top-level
            # entries in the order they are given.
            merged_config.update(yaml_data)

    return merged_config


def initialize_master(args: Args):
    """Create and configure the diagnostic master from args."""
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
    """Entry point for the diagnostic master."""
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
