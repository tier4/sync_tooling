from argparse import REMAINDER, ArgumentParser
from collections import namedtuple

import yaml
from flask import Flask, jsonify, render_template_string, request
from werkzeug.serving import WSGIRequestHandler

from diag_master.echarts_adapter import (
    HTML_TEMPLATE,
    sync_graph_to_echart_options,
)
from diag_master.ros2_adapter import Ros2Adapter
from sync_graph import SyncGraph
from sync_graph.yaml import clock_tree_to_digraph
from sync_tooling_msgs.clock_id import readable_clock_id
from sync_tooling_msgs.graph_update_pb2 import GraphUpdate
from sync_tooling_msgs.port_id import readable_port_id

Args = namedtuple("Args", ["bind_ip", "bind_port", "reference", "ros", "ros_args"])

app = Flask("diag_master")

sync_graph = SyncGraph()
ros2_adapter: Ros2Adapter | None = None


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/get_graph")
def get_graph():
    global sync_graph
    option = sync_graph_to_echart_options(sync_graph)
    return jsonify(option)


@app.route("/update_graph", methods=["POST"])
def update_graph():
    data = request.get_data()
    graph_update = GraphUpdate()
    graph_update.ParseFromString(data)
    print(f"  {graph_update.WhichOneof('update')}:")
    match graph_update.WhichOneof("update"):
        case "clock_alias_update":
            u = graph_update.clock_alias_update
            print(f"    {[readable_clock_id(a) for a in u.aliases]}")
        case "clock_diff_measurement":
            u = graph_update.clock_diff_measurement
            print(
                f"    {readable_clock_id(u.src)}->{readable_clock_id(u.dst)}: {u.diff_ns*1e-6:.3f} ms"
            )
        case "clock_master_update":
            u = graph_update.clock_master_update
            print(
                f"    {readable_clock_id(u.clock_id)} has master {readable_clock_id(u.master) if u.master else 'None'}"
            )
        # case "phc2sys_status_msg":
        #     u = graph_update.phc2sys_status_msg
        #     print(f"    {u.}")
        case "phc2sys_update":
            u = graph_update.phc2sys_update
            print(
                f"    {readable_clock_id(u.src)}->{readable_clock_id(u.dst)}: {u.clock_state}"
            )
        case "port_state_update":
            u = graph_update.port_state_update
            print(f"    {readable_port_id(u.port_id)}: {u.port_state}")
        # case "ptp4l_port_status_msg":
        #     u = graph_update.ptp4l_port_status_msg
        #     print(f"    {u.}")
        # case "ptp4l_status_msg":
        #     u = graph_update.ptp4l_status_msg
        #     print(f"    {u.}")
        case "ptp_parent_update":
            u = graph_update.ptp_parent_update
            print(
                f"    {readable_clock_id(u.clock_id)} has parent {readable_port_id(u.parent)}"
            )
        case _:
            pass

    sync_graph.update(graph_update)
    return {}


def parse_args() -> Args:
    parser = ArgumentParser()
    parser.add_argument("bind_ip")
    parser.add_argument("--bind_port", "-p", type=int, default=16161)
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


def main():
    global sync_graph
    global ros2_adapter

    args = parse_args()

    if args.reference:
        reference_graph = parse_reference_graph(args.reference)
        sync_graph = SyncGraph(reference_graph)

    ros_enabled: bool = args.ros or bool(args.ros_args)
    if ros_enabled:
        from diag_master.ros2_adapter import Ros2Adapter

        ros2_adapter = Ros2Adapter(args.ros_args or [])

    # This enables HTTP keep-alive, see
    # https://stackoverflow.com/questions/10523879/how-to-make-flask-keep-ajax-http-connection-alive
    WSGIRequestHandler.protocol_version = "HTTP/1.1"
    app.run(args.bind_ip, args.bind_port)
