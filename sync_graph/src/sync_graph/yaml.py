from typing import Literal

import networkx as nx
from networkx import DiGraph

from sync_graph.sync_graph import Config, DiffThresholds
from sync_tooling_msgs.clock_id import parse_clock_id


def get_subtree(d: dict, key: str, typ: type, yaml_path: str = ""):
    if key not in d:
        prefix = f"{yaml_path}." if yaml_path else ""
        raise ValueError(f"{prefix}{key} is required")
    return typ(d[key])


def clock_tree_to_digraph(clock_tree: dict) -> nx.DiGraph:
    """
    Transform a tree-shaped dict of clock IDs to a digraph.

    Examples:
        >>> tree = {"main.sys": {"sub.sys": {"other.sys"}}}
        >>> G = clock_tree_to_digraph(tree)
        >>> G  # main.sys -> sub.sys -> other.sys

    Args:
        clock_tree (dict): one or multiple trees of clock IDs.

    Returns:
        nx.DiGraph: The parsed, valid graph
    """

    def _tree_to_edges(
        tree: dict[str, dict | None], edges=None
    ) -> list[tuple[str, str]]:
        if edges is None:
            edges = []

        for parent, subtree in tree.items():
            if subtree is None:
                continue

            for key in subtree:
                edges.append((parent, key))

            _tree_to_edges(subtree, edges)
        return edges

    edges = _tree_to_edges(clock_tree)
    edges = [(parse_clock_id(src), parse_clock_id(dst)) for src, dst in edges]

    digraph = nx.from_edgelist(edges, create_using=nx.DiGraph)
    return digraph


def parse_unit(unit: str) -> Literal["ns", "us", "ms"]:
    match unit:
        case "ns" | "us" | "ms":
            return unit
        case _:
            raise ValueError(f"Invalid unit: {unit}")


def parse_diff_thresholds(diff_thresholds: dict) -> DiffThresholds:
    return DiffThresholds(
        unit=parse_unit(get_subtree(diff_thresholds, "unit", str)),
        warn=get_subtree(diff_thresholds, "warn", int),
        error=get_subtree(diff_thresholds, "error", int),
    )


def to_config(thresholds: dict) -> Config:
    return Config(
        master_diff_thresholds=parse_diff_thresholds(
            get_subtree(thresholds, "ptp_master", dict)
        ),
        phc2sys_diff_thresholds=parse_diff_thresholds(
            get_subtree(thresholds, "phc2sys", dict)
        ),
        measurement_diff_thresholds=parse_diff_thresholds(
            get_subtree(thresholds, "measurement", dict)
        ),
    )


def to_sync_graph_args(yaml_config: dict) -> tuple[Config, DiGraph]:
    diagnostics = get_subtree(yaml_config, "diagnostics", dict)
    thresholds = get_subtree(diagnostics, "diff_thresholds", dict)
    config = to_config(thresholds)

    clock_tree = clock_tree_to_digraph(get_subtree(yaml_config, "clock_tree", dict))
    return config, clock_tree
