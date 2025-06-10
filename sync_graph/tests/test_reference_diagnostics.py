"""
Tests for the [diagnose_reference_adherence][sync_graph.sync_graph.SyncGraph.diagnose_reference_adherence]
family of methods.
"""

from dataclasses import dataclass

import networkx as nx
import pytest

from sync_tooling_msgs.clock_master_update_pb2 import ClockMasterUpdate
from sync_tooling_msgs.diag_tree import prettify, to_diag_tree
from sync_tooling_msgs.graph_update_pb2 import GraphUpdate

from .util import (
    aggregated_status_label,
    graph_after_updates,
    make_measurement,
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
def two_links(sample_clock, nic_port, remote_clock):
    reference = nx.DiGraph()
    reference.add_edge(sample_clock, nic_port.clock_id)
    reference.add_edge(nic_port.clock_id, remote_clock)

    us = [
        make_phc2sys_link(sample_clock, nic_port.clock_id, False),
        *make_ptp_link(nic_port, remote_clock, False),
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
    for clock in g._graph.nodes:
        diag_tree = g.diagnose_single_clock_reference_adherence(clock)
        assert (
            aggregated_status_label(diag_tree) == "ok"
        ), f"with tree {prettify(diag_tree)}"


def test_different_but_compliant_graph(sample_clock, nic_port, remote_clock):
    reference = nx.DiGraph()
    reference.add_edge(sample_clock, nic_port.clock_id)
    reference.add_edge(nic_port.clock_id, remote_clock)

    us = [
        make_phc2sys_link(sample_clock, nic_port.clock_id, False),
        make_measurement(sample_clock, remote_clock, False),
    ]

    g = graph_after_updates(*us, reference=reference)

    for clock in g._graph.nodes:
        assert (
            aggregated_status_label(g.diagnose_single_clock_reference_adherence(clock))
            == "ok"
        )


def test_swapped_parents(sample_clock, nic_clock, remote_clock):
    reference = nx.DiGraph()
    reference.add_edge(sample_clock, nic_clock)
    reference.add_edge(nic_clock, remote_clock)

    us = [
        make_phc2sys_link(sample_clock, remote_clock, False),
        make_phc2sys_link(remote_clock, nic_clock, False),
    ]

    g = graph_after_updates(*us, reference=reference)

    statuses = [
        g.diagnose_single_clock_reference_adherence(clock) for clock in g._graph.nodes
    ]

    diag_tree = to_diag_tree(statuses)
    assert aggregated_status_label(diag_tree) == "error"


def test_rogue_clock(two_links, sample_clock_aliases):
    g = graph_after_updates(*two_links.updates, reference=two_links.reference)
    g.update(
        GraphUpdate(
            clock_master_update=ClockMasterUpdate(
                clock_id=sample_clock_aliases["sensor"]
            )
        )
    )

    assert aggregated_status_label(g.diagnose_reference_adherence()) == "warning"


def test_missing_clock(two_links):
    g = graph_after_updates(*two_links.updates, reference=two_links.reference)
    g._graph.remove_node(next(iter(two_links.reference.nodes())))

    assert aggregated_status_label(g.diagnose_reference_adherence()) == "error"
