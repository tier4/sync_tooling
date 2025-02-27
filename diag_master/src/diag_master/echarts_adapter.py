from diag_tree import aggregate, prettify
from sync_graph import C_MASTER, ClockId, SyncGraph
from sync_tooling_msgs.clock_id import readable_clock_id
from sync_tooling_msgs.diag_status_pb2 import DiagStatus
from sync_tooling_msgs.diag_tree_pb2 import DiagTree
from sync_tooling_msgs.port_id import readable_port_id
from sync_tooling_msgs.port_id_pb2 import PortId
from sync_tooling_msgs.unknown_pb2 import Unknown

DIAG_PALETTE = {
    "unknown": "#264653",
    "ok": "#2a9d8f",
    "warning": "#e9c46a",
    "error": "#e76f51",
}

HTML_TEMPLATE = """
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


def sync_graph_to_echart_data_(sg: SyncGraph) -> tuple[list, list]:
    data = []
    g = sg._graph

    for n, node_data in g.nodes.items():
        n: ClockId
        master: ClockId = node_data.get(C_MASTER)
        data.append(
            {
                "name": readable_clock_id(n),
                "x": 0,
                "y": 0,
                "tooltip": {
                    "formatter": f"Master: {readable_clock_id(master) if master else None}"
                },
            }
        )

    links = []
    for src, dst in g.edges:
        src: ClockId
        dst: ClockId
        link = sg.get_link(src, dst)
        match link:
            case PortId() as port_id:
                label = f"PTP (port {readable_port_id(port_id)} -> {readable_clock_id(dst)})"
            case DiagTree():
                label = "PHC2SYS"
            case _:
                assert False

        diag_tree = sg.diagnose_link(src, dst)
        if diag_tree is None:
            diag_tree = DiagTree(status=DiagStatus(unknown=Unknown(msg="Not received yet")))
        diag_status = aggregate(diag_tree)
        severity = diag_status.WhichOneof("status")
        if severity is None:
            assert False
        diag_color = DIAG_PALETTE[severity]
        diag_json = prettify(diag_tree)
        extended_label = "\n".join([label, diag_json])

        links.append(
            {
                "source": readable_clock_id(src),
                "target": readable_clock_id(dst),
                "lineStyle": {"color": diag_color},
                "label": {"show": True, "formatter": label},
                "select": {"label": {"show": True, "formatter": extended_label}},
            }
        )

    return data, links


def sync_graph_to_echart_options(sg: SyncGraph):
    data, links = sync_graph_to_echart_data_(sg)

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

    return option
