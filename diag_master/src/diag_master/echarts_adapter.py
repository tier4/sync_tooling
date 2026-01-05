"""Adapter for converting sync graph to ECharts visualization format."""

from typing import Any

import networkx as nx
from networkx import DiGraph
from sync_graph.sync_graph import SyncGraph
from sync_tooling_msgs.clock_id import readable_clock_id, readable_clock_type
from sync_tooling_msgs.clock_id_pb2 import ClockId
from sync_tooling_msgs.diag_status_pb2 import DiagStatus
from sync_tooling_msgs.diag_tree import aggregate, to_diag_tree
from sync_tooling_msgs.diag_tree_pb2 import DiagTree
from sync_tooling_msgs.port_id_pb2 import PortId
from sync_tooling_msgs.slave_clock_state_pb2 import SlaveClockState
from sync_tooling_msgs.unknown_pb2 import Unknown

# Currently not optimized for dark mode
DIAG_PALETTE = {
    "unknown": "#264653",
    "ok": "#2a9d8f",
    "warning": "#e9c46a",
    "error": "#e76f51",
}

NOT_RECEIVED_DIAG = to_diag_tree(Unknown(msg="Not received yet"))
REFERENCE_ONLY_DIAG = to_diag_tree(Unknown(msg="Reference link only"))


def get_status_color(status: DiagStatus):
    """Get the color for a diagnostic status."""
    if (severity := status.WhichOneof("status")) is not None:
        return DIAG_PALETTE[severity]
    return DIAG_PALETTE["unknown"]


def _pretty_status_html(status: DiagStatus):
    """Format a diagnostic status as colored HTML."""
    status_color = get_status_color(status)
    status_type = status.WhichOneof("status")
    if status_type is None:
        raise AssertionError("Got an empty status")

    msg = getattr(status, status_type).msg
    return f'<span style="color: {status_color}">{msg}</span>'


def _pretty_diag_html(diag: DiagTree):
    """Format a diagnostic tree as nested HTML."""
    match diag.WhichOneof("tree"):
        case "status":
            return _pretty_status_html(diag.status)
        case "list":
            items = [f"<li>{_pretty_diag_html(t)}</li>" for t in diag.list.list]
            return "<ul>" + "".join(items) + "</ul>"
        case "map":
            items = [
                f"<li>{k}: {_pretty_diag_html(v)}</li>" for k, v in diag.map.map.items()
            ]
            return "<ul>" + "".join(items) + "</ul>"
        case "comment":
            return f"<span>{diag.comment}</span>"
        case _:
            raise AssertionError("Got an invalid diagnostic tree")


def _clock_aliases_to_description(sg: SyncGraph, clock: ClockId):
    """Generate HTML description of clock aliases."""
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
    """Generate HTML description of port diagnostics."""
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
            ports_html += (
                f"<li>{port.port_number}: {_pretty_status_html(aggregate(diag))}</li>"
            )
        ports_html += "</ul></li>"
    ports_html += "</ul>"
    return ports_html


def _clock_to_echart_data(
    sg: SyncGraph, clock: ClockId, position: tuple[float, float] | None = None
):
    """Convert a clock node to ECharts node data."""
    extended_description = []

    if clock in sg._graph:
        aliases_description = _clock_aliases_to_description(sg, clock)
        extended_description.append(aliases_description)

        ports_description = _port_diags_to_description(sg, clock)
        extended_description.append(ports_description)

        diag = sg.diagnose_clock(clock)
        extended_description.append("Diagnostics:")
        extended_description.append(_pretty_diag_html(diag))

        status = aggregate(diag)
        status_color = get_status_color(status)
        is_reference_only = False
    else:
        status_color = DIAG_PALETTE["error"]
        extended_description.append("Clock not found in graph")
        is_reference_only = True

    node: dict[str, Any] = {
        "name": readable_clock_id(clock),
        "tooltip": {"formatter": "<br/>".join(extended_description)},
        "itemStyle": {"color": status_color},
        "label": {"show": True, "position": "right"},
    }

    # Add dashed border and no filling for reference-only clocks
    if is_reference_only:
        item_style: dict[str, Any] = node["itemStyle"]
        item_style["borderColor"] = status_color
        item_style["borderWidth"] = 2
        item_style["borderType"] = "dashed"
        item_style["color"] = "transparent"

    if position is not None:
        node["x"] = position[0]
        node["y"] = position[1]
        node["fixed"] = True
    else:
        node["x"] = 0
        node["y"] = 0
        node["fixed"] = False

    return node


def _link_to_echart_link(sg: SyncGraph, src: ClockId, dst: ClockId):
    extended_description = []
    link_labels = []
    is_pseudo_link = True
    is_reference_link = (
        sg.reference_graph is not None and (src, dst) in sg.reference_graph.edges()
    )

    if is_reference_link:
        link_labels.append("Reference")
        extended_description.append("Reference link")

    links = sg.get_links(src, dst)
    is_real_link = len(links) > 0

    for type, metadata in links:
        match type, metadata:
            case "ptp_parent", PortId() as port_id:
                is_pseudo_link = False
                link_labels.append(f"PTP {port_id.ptp_domain}")
            case "phc2sys", SlaveClockState():
                is_pseudo_link = False
                link_labels.append("PHC2SYS")
            case "measurement", int():
                link_labels.append("Measurement")
            case "master", int():
                link_labels.append("Master")
            case _:
                raise AssertionError()

    if is_real_link:
        diag = sg.diagnose_link(src, dst) or NOT_RECEIVED_DIAG
    elif is_reference_link:
        diag = REFERENCE_ONLY_DIAG
    else:
        raise AssertionError()

    extended_description.append("Diagnostics:")
    extended_description.append(_pretty_diag_html(diag))

    status = aggregate(diag)
    status_color = get_status_color(status)

    return {
        "source": readable_clock_id(src),
        "target": readable_clock_id(dst),
        "lineStyle": {
            "color": status_color,
            "type": "dashed" if is_pseudo_link else "solid",
        },
        "label": {"show": True, "formatter": ", ".join(link_labels)},
        "tooltip": {"formatter": "<br/>".join(extended_description)},
    }


def _layout_circular(g: DiGraph) -> dict[ClockId, tuple[float, float]]:
    """Lay out a tree-like graph in a concentric manner.

    A root node in the center is surrounded by
    concentric rings roughly equivalent to the topological generations of the graph.

    See https://graphviz.org/docs/layouts/twopi/ for more information.

    Args:
        g: The graph to layout.

    Returns:
        A dictionary mapping each node to the layout position (x, y).

    """
    h = nx.convert_node_labels_to_integers(g, label_attribute="node_label")
    layout = nx.nx_pydot.pydot_layout(h, prog="twopi")
    return {h.nodes[n]["node_label"]: p for n, p in layout.items()}


def _is_node_in_cycle(g: DiGraph, n: ClockId) -> bool:
    try:
        nx.find_cycle(g, source=n)  # type: ignore
        return True
    except nx.NetworkXNoCycle:
        return False


def _get_clock_positions(
    sg: SyncGraph,
) -> dict[ClockId, tuple[float, float] | None] | None:
    if sg.reference_graph is None:
        return None

    g = sg._graph
    r: DiGraph = sg.reference_graph.copy()  # type: ignore
    assert nx.is_tree(r)
    mapping = {n: sg.get_canonical_clock_id(n) for n in r.nodes}
    r = nx.relabel_nodes(r, mapping)  # type: ignore
    r.remove_edges_from(nx.selfloop_edges(r))
    assert nx.is_tree(r)

    r_levels = list(nx.topological_generations(r))

    # Compute the set of nodes that are not in the reference (rogue clocks) that still can be nicely
    # laid out.
    #
    # A node can be laid out if:
    # - it is not part of a cycle
    # - there exists a relative (descendant or ancestor) that is in the reference
    nodes_not_in_reference = set(g.nodes) - set(r.nodes)

    edges_to_add = []
    for n in nodes_not_in_reference:
        if _is_node_in_cycle(g, n):
            continue

        relatives = nx.descendants(g, n) | nx.ancestors(g, n)
        relatives = [n for n in relatives if r.has_node(n)]
        if not relatives:
            continue

        # Find the relative furthest down the hierarchy
        def get_level(n: ClockId) -> int:
            for i, level in enumerate(r_levels):
                if n in level:
                    return i
            raise AssertionError(
                "Node in reference has to appear in its topological generations"
            )

        # Ensure stability across additions/removals by sorting by ID
        relatives = sorted(relatives, key=readable_clock_id)
        furthest_relative: ClockId = max(relatives, key=get_level)
        # This edge is only for lay-outing purposes. It does not appear in the visualization.
        edges_to_add.append((furthest_relative, n))

    r.add_edges_from(edges_to_add)

    # Run the tree layout algorithm
    layout = _layout_circular(r)  # type: ignore

    layout: dict[ClockId, tuple[float, float] | None] = {
        sg.get_canonical_clock_id(n): pos for n, pos in layout.items()
    }

    for clock_id in sg._graph.nodes:
        if clock_id in layout:
            continue

        layout[clock_id] = None

    return layout


def _sync_graph_to_echart_data_and_links(
    sg: SyncGraph,
) -> tuple[list, list]:
    data = []
    links = []

    g = sg._graph

    positions = _get_clock_positions(sg)
    if positions is not None:
        # Only clocks present in the reference graph are laid out in a fixed manner.
        for clock_id, position in positions.items():
            node = _clock_to_echart_data(sg, clock_id, position)
            data.append(node)
    else:
        # All other clocks are laid out in a force-directed manner.
        for clock_id in g.nodes:
            node = _clock_to_echart_data(sg, clock_id)
            data.append(node)

    real_edges = set(g.edges())
    reference_edges = (
        set(sg.reference_graph.edges()) if sg.reference_graph is not None else set()
    )
    for src, dst in real_edges | reference_edges:
        src: ClockId
        dst: ClockId

        edge_link = _link_to_echart_link(sg, src, dst)
        links.append(edge_link)

    return data, links


def sync_graph_to_echart_options(sg: SyncGraph):
    """Convert a SyncGraph to an ECharts options dict containing a graph series."""
    data, links = _sync_graph_to_echart_data_and_links(sg)

    option = {
        "title": {"text": "Synchronization Graph"},
        "tooltip": {"trigger": "item"},
        "series": [
            {
                "type": "graph",
                "layout": "force",
                "force": {
                    "repulsion": 1,
                    "gravity": 0.2,
                    "layoutAnimation": False,
                },
                "roam": True,
                "label": {"show": True},
                "symbolSize": 20,
                "itemStyle": {"color": "#264653"},
                "edgeSymbol": [None, "arrow"],
                "edgeSymbolSize": 20,
                "autoCurveness": False,
                "data": data,
                "links": links,
            }
        ],
    }

    return option
