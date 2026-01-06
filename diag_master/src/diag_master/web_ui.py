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

"""Flask-based web UI for visualizing the sync graph."""

from threading import Thread

from flask import Flask, render_template
from flask_socketio import SocketIO
from sync_graph.sync_graph import SyncGraph

from diag_master.echarts_adapter import sync_graph_to_echart_options


class WebUi:
    """Web UI server for real-time sync graph visualization.

    Warning: The web UI is currently using a Flask development server, which is not secure or
    particularly performant. It is recommended to run the web UI only in trusted environments.

    This component serves a web UI on `http://0.0.0.0:5000` and pushes real-time updates to the
    UI via WebSockets whenever the sync graph is updated.
    """

    def __init__(self):
        """Initialize Flask app and WebSocket."""
        self._app = Flask(__name__)
        self._web_socket = SocketIO(self._app)

        @self._app.route("/")
        def index():
            return render_template("index.html")

    def update(self, sg: SyncGraph):
        """Push updated graph data to connected clients via WebSockets."""
        echart_options = sync_graph_to_echart_options(sg)
        self._web_socket.emit("update_event", echart_options)

    def run(self):
        """Start the web server in a background thread."""
        self._thread = Thread(target=self._app.run, args=("0.0.0.0", 5000), daemon=True)
        self._thread.start()
