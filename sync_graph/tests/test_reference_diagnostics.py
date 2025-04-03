"""
Tests for the [diagnose_reference_adherence][sync_graph.sync_graph.SyncGraph.diagnose_reference_adherence]
family of methods.
"""

import pytest

from .util import (
    aggregated_status_label,
    graph_after_updates,
    make_phc2sys_link,
    make_ptp_link,
)


@pytest.mark.parametrize("graph_shape", ["empty", "two_links"])
def test_without_reference(
    sample_clock_ids, nic_port_id, remote_clock_ids, graph_shape
):
    """
    A graph without a reference graph shall be diagnosed as `Ok`.
    """

    test_cases = {
        "empty": [],
        "two_links": [
            make_phc2sys_link(sample_clock_ids["system"], nic_port_id.clock_id, False),
            *make_ptp_link(nic_port_id, remote_clock_ids["ptp"], False),
        ],
    }

    g = graph_after_updates(*test_cases[graph_shape])
    assert aggregated_status_label(g.diagnose_reference_adherence()) == "ok"
