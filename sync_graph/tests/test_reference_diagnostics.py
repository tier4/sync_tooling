"""
Tests for the [diagnose_reference_adherence][sync_graph.sync_graph.SyncGraph.diagnose_reference_adherence]
family of methods.
"""

from dataclasses import dataclass

import networkx as nx
import pytest

from sync_tooling_msgs.diag_tree import prettify
from sync_tooling_msgs.graph_update_pb2 import GraphUpdate

from .util import (
    aggregated_status_label,
    graph_after_updates,
    make_phc2sys_link,
    make_ptp_link,
)


@dataclass
class GraphArgs:
    updates: list[GraphUpdate]
    reference: nx.DiGraph | None


@pytest.fixture
def empty():
    return GraphArgs([], nx.DiGraph())


@pytest.fixture
def two_links(sample_clock_ids, nic_port_id, remote_clock_ids):
    reference = nx.DiGraph()
    reference.add_edge(sample_clock_ids["system"], nic_port_id.clock_id)
    reference.add_edge(nic_port_id.clock_id, remote_clock_ids["ptp"])

    us = [
        make_phc2sys_link(sample_clock_ids["system"], nic_port_id.clock_id, False),
        *make_ptp_link(nic_port_id, remote_clock_ids["ptp"], False),
    ]

    return GraphArgs(us, reference)


@pytest.mark.parametrize("graph_name", ["empty", "two_links"])
def test_without_reference(graph_name, request):
    """
    A graph without a reference graph shall be diagnosed as `Ok`.
    """

    graph_args: GraphArgs = request.getfixturevalue(graph_name)
    g = graph_after_updates(*graph_args.updates)
    assert aggregated_status_label(g.diagnose_reference_adherence()) == "ok"


@pytest.mark.parametrize("graph_name", ["empty", "two_links"])
def test_perfect_reference_match(graph_name, request):
    graph_args: GraphArgs = request.getfixturevalue(graph_name)
    g = graph_after_updates(*graph_args.updates, reference=graph_args.reference)
    diag_tree = g.diagnose_reference_adherence()
    assert (
        aggregated_status_label(diag_tree) == "ok"
    ), f"with tree {prettify(diag_tree)}"
