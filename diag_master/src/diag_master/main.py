import socket

from quart import Quart, jsonify, render_template_string, Response

from diag_tree import Unknown, Ok, Warning, Error, aggregate, prettify
from sync_graph import Clock, ClockId, Phc2SysSyncLink, PtpSyncLink, SyncGraph


from tcp_transport import JsonSubscription
from sync_graph import GraphUpdate
import asyncio

from argparse import ArgumentParser

app = Quart("diag_master")
master: "DiagMaster | None" = None

DIAG_PALETTE = {Unknown: "#264653", Ok: "#2a9d8f", Warning: "#e9c46a", Error: "#e76f51"}


@app.route("/")
async def index():
    # HTML template for the webpage
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdn.jsdelivr.net/npm/echarts/dist/echarts.min.js"></script>
    </head>
    <body style="overflow: hidden;">
        <div id="chart" style="width: 100vw; height: 100vh;"></div>
        <script>
            var chart = echarts.init(document.getElementById('chart'));

            window.onresize = function() {
                chart.resize();
            };

            function fetchGraphData() {
                fetch('/get_graph')
                    .then(response => response.json())
                    .then(data => {
                        chart.setOption(data);
                    });
            }

            // Fetch data every 1 second
            setInterval(fetchGraphData, 1000);

            // Initial fetch
            fetchGraphData();
        </script>
    </body>
    </html>
    """
    return await render_template_string(html)


def sync_graph_to_echart(sg: SyncGraph) -> tuple[list, list]:
    data = []
    K = sg._DATA_KEY
    g = sg._graph

    for n, node_data in g.nodes.items():
        n: ClockId
        clock: Clock = node_data[K]
        data.append(
            {
                "name": n.id(),
                "x": 0,
                "y": 0,
                "tooltip": {
                    "formatter": f"Master: {clock.master_id.id() if clock.master_id else None}"
                },
            }
        )

    links = []
    for src, dst in g.edges:
        src: ClockId
        dst: ClockId
        link = sg.get_link(src, dst)
        match link:
            case PtpSyncLink(src_port, dst_port):
                label = f"PTP (port {src_port.port_number} -> {dst_port.port_number})"
            case Phc2SysSyncLink():
                label = "PHC2SYS"
            case _:
                assert False

        diag = sg.diagnose_link(link)
        diag_status = aggregate(diag)
        diag_color = DIAG_PALETTE[diag_status.__class__]
        diag_json = prettify(diag)
        extended_label = "\n".join([label, diag_json])

        links.append(
            {
                "source": src.id(),
                "target": dst.id(),
                "lineStyle": {"color": diag_color},
                "label": {"show": True, "formatter": label},
                "select": {"label": {"show": True, "formatter": extended_label}},
            }
        )

    return data, links


@app.route("/get_graph")
def get_graph():
    global master
    if master is None:
        return Response(status=404)

    g = master.sync_graph_
    data, links = sync_graph_to_echart(g)

    option = {
        "title": {"text": "Synchronization Graph"},
        "series": [
            {
                "type": "graph",
                "layout": "force",
                "selectedMode": True,
                "roam": True,
                "label": {"show": True, "fontSize": 20},
                "symbolSize": 300,
                "itemStyle": {"color": "#264653"},
                "edgeSymbol": [None, "arrow"],
                "edgeSymbolSize": 20,
                "edgeLabel": {"fontSize": 20},
                "data": data,
                "links": links,
            }
        ],
    }

    return jsonify(option)


class DiagMaster:
    def __init__(self, bind_ip: str, bind_port: int) -> None:
        hostname = socket.gethostname()
        if not hostname:
            raise RuntimeError("Could not determine hostname")

        self.subscription_ = JsonSubscription(
            bind_ip,
            bind_port,
            self.json_callback,
            {GraphUpdate},  # type: ignore
        )

        self.sync_graph_ = SyncGraph()

    async def run(self):
        return self.subscription_.listen()

    def json_callback(self, j):
        try:
            self.sync_graph_.update(j)
        except InterruptedError as e:
            raise e
        except Exception as e:
            print(f"error: {e}")


def main():
    global master

    parser = ArgumentParser()
    parser.add_argument("bind_ip")
    parser.add_argument("--bind_port", "-p", type=int, default=16161)
    args = parser.parse_args()
    master = DiagMaster(args.bind_ip, args.bind_port)
    tasks = [master.run(), app.run_task()]

    loop = asyncio.get_event_loop()
    group = asyncio.gather(*tasks)
    loop.run_until_complete(group)
