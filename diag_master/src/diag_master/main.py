from werkzeug.serving import WSGIRequestHandler
from diag_master.echarts_adapter import (
    HTML_TEMPLATE,
    sync_graph_to_echart_options,
)
from flask import Flask, jsonify, render_template_string, request

from sync_graph import SyncGraph

from sync_tooling_msgs.graph_update_pb2 import GraphUpdate


from argparse import ArgumentParser

app = Flask("diag_master")

sync_graph = SyncGraph()


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
    sync_graph.update(graph_update)
    return {}


def main():
    parser = ArgumentParser()
    parser.add_argument("bind_ip")
    parser.add_argument("--bind_port", "-p", type=int, default=16161)
    args = parser.parse_args()

    # This enables HTTP keep-alive, see
    # https://stackoverflow.com/questions/10523879/how-to-make-flask-keep-ajax-http-connection-alive
    WSGIRequestHandler.protocol_version = "HTTP/1.1"
    app.run(args.bind_ip, args.bind_port)
