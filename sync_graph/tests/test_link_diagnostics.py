import pytest

from .util import (
    assert_aggregated_status,
    graph_after_updates,
    make_master_link,
    make_measurement,
    make_phc2sys_link,
    make_ptp_link,
)


@pytest.mark.parametrize("is_faulty,expected_status", [(True, "error"), (False, "ok")])
@pytest.mark.parametrize("link_type", ["phc2sys", "ptp", "master", "measurement"])
def test_link_diagnostics(
    nic_port_id, sample_clock_ids, is_faulty, expected_status, link_type
):
    src_port = nic_port_id
    src = src_port.clock_id
    dst = sample_clock_ids["system"]

    match link_type:
        case "master":
            us = [make_master_link(src, dst, is_faulty)]
        case "measurement":
            us = [make_measurement(src, dst, is_faulty)]
        case "phc2sys":
            us = [make_phc2sys_link(src, dst, is_faulty)]
        case "ptp":
            us = make_ptp_link(src_port, dst, is_faulty)
        case _:
            raise AssertionError()

    g = graph_after_updates(*us)
    diag_tree = g.diagnose_link(src, dst)
    assert_aggregated_status(diag_tree, expected_status)
