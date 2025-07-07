from threading import Thread

from flask import Flask, render_template
from flask_socketio import SocketIO

from diag_master.echarts_adapter import sync_graph_to_echart_options
from sync_graph.sync_graph import SyncGraph


class WebUi:
    def __init__(self):
        self._app = Flask(__name__)
        self._web_socket = SocketIO(self._app)

        @self._app.route("/")
        def index():
            return render_template("index.html")

    def update(self, sg: SyncGraph):
        echart_options = sync_graph_to_echart_options(sg)
        self._web_socket.emit("update_event", echart_options)

    def run(self):
        self._thread = Thread(target=self._app.run, args=("0.0.0.0", 5000), daemon=True)
        self._thread.start()
