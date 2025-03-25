from argparse import REMAINDER, ArgumentParser
from collections import namedtuple
from datetime import timedelta

import yaml
from flask import Flask, jsonify, render_template_string, request
from networkx import DiGraph
from werkzeug.serving import WSGIRequestHandler

from diag_master.echarts_adapter import (
    HTML_TEMPLATE,
    sync_graph_to_echart_options,
)
from diag_master.ros2_adapter import Ros2Adapter
from sync_graph.sync_graph import SyncGraph
from sync_graph.timed_graph_update_queue import TimedGraphUpdateQueue
from sync_graph.yaml import clock_tree_to_digraph
from sync_tooling_msgs.graph_update_pb2 import GraphUpdate

Args = namedtuple(
    "Args", ["bind_ip", "bind_port", "reference", "ros", "ros_args", "update_expiry_s"]
)


class AppState:
    def __init__(
        self,
        reference_graph: DiGraph | None,
        ros2_adapter: Ros2Adapter | None,
        update_expiry: timedelta,
    ) -> None:
        self._reference_graph = reference_graph
        self._ros2_adapter = ros2_adapter
        self._update_queue = TimedGraphUpdateQueue(update_expiry)

    def update(self, u: GraphUpdate):
        self._update_queue.push(u)

    @property
    def sync_graph(self):
        sg = SyncGraph(self._reference_graph)
        for u in self._update_queue.updates:
            sg.update(u)
        return sg


app = Flask("diag_master")


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/get_graph")
def get_graph():
    global app_state
    option = sync_graph_to_echart_options(app_state.sync_graph)
    return jsonify(option)


@app.route("/update_graph", methods=["POST"])
def update_graph():
    global app_state

    data = request.get_data()
    graph_update = GraphUpdate()
    graph_update.ParseFromString(data)
    app_state.update(graph_update)
    return {}


def parse_args() -> Args:
    parser = ArgumentParser()
    parser.add_argument("bind_ip")
    parser.add_argument("--bind_port", "-p", type=int, default=16161)
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
        "--ros",
        action="store_true",
        help="Enables ROS 2 interaction. Passing `--ros-args` implicitly enables ROS 2 interaction.",
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


def initial_state_from_args(args: Args):
    reference_graph = parse_reference_graph(args.reference) if args.reference else None

    ros_enabled: bool = args.ros or bool(args.ros_args)
    ros2_adapter = Ros2Adapter(args.ros_args or []) if ros_enabled else None

    update_expiry = timedelta(seconds=args.update_expiry_s)

    return AppState(reference_graph, ros2_adapter, update_expiry)


def main():
    global app_state

    args = parse_args()
    app_state = initial_state_from_args(args)

    # This enables HTTP keep-alive, see
    # https://stackoverflow.com/questions/10523879/how-to-make-flask-keep-ajax-http-connection-alive
    WSGIRequestHandler.protocol_version = "HTTP/1.1"
    app.run(args.bind_ip, args.bind_port)
