from diag_tree import aggregate, prettify
from sync_graph import C_MASTER, ClockId, SyncGraph
from sync_tooling_msgs.clock_id import readable_clock_id, readable_clock_type
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


def clock_to_echart_data_(clock: ClockId, metadata: dict, aliases: list[ClockId]):
    data = []
    links = []

    extended_description = []

    master: ClockId | None = metadata.get(C_MASTER)

    if master is None:
        extended_description.append("No master")
    elif master == clock:
        extended_description.append("Grandmaster")
    else:
        extended_description.append(f"Master: {readable_clock_id(master)}")
        links.append(
            {
                "source": readable_clock_id(master),
                "target": readable_clock_id(clock),
                "label": {"show": True, "formatter": "PTP Master"},
                "lineStyle": {
                    "color": DIAG_PALETTE["unknown"],
                    "type": "dashed",
                    "curveness": 0.2,
                },
            }
        )

    aliases_html = "Known aliases: "
    aliases = [a for a in aliases if a != clock]
    if aliases:
        aliases_html += "<ul>"
        for alias in aliases:
            aliases_html += (
                f"<li>{readable_clock_type(alias)}: {readable_clock_id(alias)}</li>"
            )
        aliases_html += "</ul>"
    else:
        aliases_html += "None"

    extended_description.append(aliases_html)
    extended_description = "<br/>".join(extended_description)

    data.append(
        {
            "name": readable_clock_id(clock),
            "x": 0,
            "y": 0,
            "tooltip": {"formatter": extended_description},
        }
    )

    return data, links


def link_to_echart_data_(
    src: ClockId, dst: ClockId, metadata: DiagTree | PortId, diag: DiagTree
):
    links = []

    extended_description = []

    match metadata:
        case PortId() as port_id:
            label = "PTP"
            extended_description.append(f"Parent port: {readable_port_id(port_id)}")
        case DiagTree():
            label = "PHC2SYS"
        case _:
            assert False

    status = aggregate(diag)
    severity = status.WhichOneof("status")
    if severity is None:
        assert False
    diag_color = DIAG_PALETTE[severity]
    extended_description.append(prettify(diag))
    extended_description = "<br/>".join(extended_description)

    links.append(
        {
            "source": readable_clock_id(src),
            "target": readable_clock_id(dst),
            "lineStyle": {"color": diag_color},
            "label": {"show": True, "formatter": label},
            "tooltip": {"formatter": extended_description},
        }
    )

    return (), links


def sync_graph_to_echart_data_(sg: SyncGraph) -> tuple[list, list]:
    data = []
    links = []

    g = sg._graph

    for clock_id, metadata in g.nodes.items():
        node_data, node_links = clock_to_echart_data_(
            clock_id, metadata, sg.get_sorted_aliases(clock_id)
        )

        data += node_data
        links += node_links

    for src, dst in g.edges:
        src: ClockId
        dst: ClockId
        link = sg.get_link(src, dst)
        diag = sg.diagnose_link(src, dst)
        if diag is None:
            diag = DiagTree(status=DiagStatus(unknown=Unknown(msg="Not received yet")))

        edge_data, edge_links = link_to_echart_data_(src, dst, link, diag)
        data += edge_data
        links += edge_links

    return data, links


def sync_graph_to_echart_options(sg: SyncGraph):
    data, links = sync_graph_to_echart_data_(sg)

    option = {
        "title": {"text": "Synchronization Graph"},
        "tooltip": {"trigger": "item"},
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
