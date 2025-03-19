import networkx as nx

from sync_tooling_msgs.clock_id import parse_clock_id


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
