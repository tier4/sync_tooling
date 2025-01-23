from json import JSONDecodeError
import sys
from typing import get_args

from diag_master.echarts_adapter import (
    HTML_TEMPLATE,
    sync_graph_to_echart_options,
)
from flask import Flask, jsonify, render_template_string, request
from flask_api import status

from http_transport import DataclassJsonDecoder
from sync_graph import SyncGraph


from sync_graph import GraphUpdate

from argparse import ArgumentParser

app = Flask("diag_master")

sync_graph = SyncGraph()
decoder = DataclassJsonDecoder({GraphUpdate})


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
    if not request.is_json:
        return "Expected JSON MIME-type", status.HTTP_415_UNSUPPORTED_MEDIA_TYPE

    try:
        obj = decoder.decode(request.get_data(cache=False, as_text=True))
    except JSONDecodeError:
        app.log_exception(sys.exc_info())
        return "Could not decode JSON", status.HTTP_400_BAD_REQUEST

    if not isinstance(obj, get_args(GraphUpdate)):
        return "Not a valid graph update", status.HTTP_400_BAD_REQUEST

    sync_graph.update(obj)
    return {}


def main():
    parser = ArgumentParser()
    parser.add_argument("bind_ip")
    parser.add_argument("--bind_port", "-p", type=int, default=16161)
    args = parser.parse_args()

    app.run(args.bind_ip, args.bind_port)
