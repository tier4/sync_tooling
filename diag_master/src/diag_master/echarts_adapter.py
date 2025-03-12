from sync_graph import ClockId, SyncGraph
from sync_tooling_msgs.clock_id import readable_clock_id, readable_clock_type
from sync_tooling_msgs.diag_status_pb2 import DiagStatus
from sync_tooling_msgs.diag_tree import aggregate, prettify, to_diag_tree
from sync_tooling_msgs.diag_tree_pb2 import DiagTree
from sync_tooling_msgs.port_id import readable_port_id
from sync_tooling_msgs.port_id_pb2 import PortId
from sync_tooling_msgs.servo_state import diagnose_servo_state
from sync_tooling_msgs.slave_clock_state_pb2 import SlaveClockState
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

NOT_RECEIVED_DIAG = to_diag_tree(Unknown(msg="Not received yet"))


def get_status_color(status: DiagStatus):
    if (severity := status.WhichOneof("status")) is not None:
        return DIAG_PALETTE[severity]
    return DIAG_PALETTE["unknown"]


def _pretty_diag_html(diag: DiagTree):
    status = aggregate(diag)
    status_color = get_status_color(status)
    return f'<span style="color: {status_color}">{prettify(diag)}</span>'


def _clock_master_to_echart_data(sg: SyncGraph, clock: ClockId):
    master = sg.get_master(clock)

    if master is None:
        return "No master", []
    elif master == clock:
        return "Grandmaster", []
    else:
        master_description = f"Master: {readable_clock_id(master)}"
        link = {
            "source": readable_clock_id(master),
            "target": readable_clock_id(clock),
            "label": {"show": True, "formatter": "PTP Master"},
            "lineStyle": {
                "color": DIAG_PALETTE["unknown"],
                "type": "dashed",
                "curveness": 0.2,
            },
        }

        return master_description, [link]


def _clock_aliases_to_description(sg: SyncGraph, clock: ClockId):
    aliases = [a for a in sg.get_sorted_aliases(clock) if a != clock]

    aliases_html = "Known aliases: "
    if not aliases:
        return aliases_html + "None"

    aliases_html += "<ul>"
    for alias in aliases:
        aliases_html += (
            f"<li>{readable_clock_type(alias)}: {readable_clock_id(alias)}</li>"
        )
    aliases_html += "</ul>"

    return aliases_html


def _port_diags_to_description(sg: SyncGraph, clock: ClockId):
    ports = sorted(sg.get_ports(clock), key=lambda port: port.port_number)

    ports_html = "PTP ports: "
    if not ports:
        return ports_html + "None"

    ports_html += "<ul>"
    domains = sorted({port.ptp_domain for port in ports})
    for domain in domains:
        ports_html += f"<li>Domain {domain}:<ul>"
        for port in ports:
            diag = sg.diagnose_port(port) or NOT_RECEIVED_DIAG
            ports_html += f"<li>{port.port_number}: {_pretty_diag_html(diag)}</li>"
        ports_html += "</ul></li>"
    ports_html += "</ul>"
    return ports_html


def _clock_to_echart_data(sg: SyncGraph, clock: ClockId):
    data = []
    links = []
    extended_description = []

    master_description, master_links = _clock_master_to_echart_data(sg, clock)
    extended_description.append(master_description)
    links += master_links

    aliases_description = _clock_aliases_to_description(sg, clock)
    extended_description.append(aliases_description)

    ports_description = _port_diags_to_description(sg, clock)
    extended_description.append(ports_description)

    diag = sg.diagnose_clock(clock)
    status = aggregate(diag)
    status_color = get_status_color(status)

    data.append(
        {
            "name": readable_clock_id(clock),
            "x": 0,
            "y": 0,
            "tooltip": {"formatter": "<br/>".join(extended_description)},
            "itemStyle": {"color": status_color},
        }
    )

    return data, links


def _link_to_echart_link(sg: SyncGraph, src: ClockId, dst: ClockId):
    extended_description = []

    link = sg.get_link(src, dst)

    match link:
        case PortId() as port_id:
            label = f"PTP {port_id.ptp_domain}"
            extended_description.append(f"PTP domain: {port_id.ptp_domain}")
            extended_description.append(
                f"Parent port: {readable_port_id(port_id, False)}"
            )
            port_diag = sg.diagnose_port(port_id)
            extended_description.append(
                f"Parent port state: {_pretty_diag_html(port_diag)}"
            )
        case SlaveClockState() as state:
            label = "PHC2SYS"
            servo_diag = diagnose_servo_state(state.servo_state)
            extended_description.append(
                f"Master offset: {state.offset_ns / 1e3:.0f} µs"
            )
            extended_description.append(f"Sync delay: {state.delay_ns / 1e3:.0f} µs")
            extended_description.append(
                f"Frequency offset: {state.frequency_offset_ppb} ppb"
            )
            extended_description.append(f"Servo state: {_pretty_diag_html(servo_diag)}")
        case _:
            raise AssertionError()

    diag = sg.diagnose_link(src, dst) or NOT_RECEIVED_DIAG
    status = aggregate(diag)
    status_color = get_status_color(status)

    return {
        "source": readable_clock_id(src),
        "target": readable_clock_id(dst),
        "lineStyle": {"color": status_color},
        "label": {"show": True, "formatter": label},
        "tooltip": {"formatter": "<br/>".join(extended_description)},
    }


def _sync_graph_to_echart_data_and_links(sg: SyncGraph) -> tuple[list, list]:
    data = []
    links = []

    g = sg._graph

    for clock_id in g.nodes:
        node_data, node_links = _clock_to_echart_data(sg, clock_id)

        data += node_data
        links += node_links

    for src, dst in g.edges:
        src: ClockId
        dst: ClockId

        edge_link = _link_to_echart_link(sg, src, dst)
        links.append(edge_link)

    return data, links


def sync_graph_to_echart_options(sg: SyncGraph):
    data, links = _sync_graph_to_echart_data_and_links(sg)

    option = {
        "title": {"text": "Synchronization Graph"},
        "tooltip": {"trigger": "item"},
        "series": [
            {
                "type": "graph",
                "layout": "force",
                "roam": True,
                "label": {"show": True, "fontSize": 20},
                "symbolSize": 300,
                "itemStyle": {"color": "#264653"},
                "edgeSymbol": [None, "arrow"],
                "edgeSymbolSize": 20,
                "edgeLabel": {"fontSize": 20},
                "animation": False,
                "data": data,
                "links": links,
            }
        ],
    }

    return option
