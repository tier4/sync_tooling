import pytest

from sync_tooling_msgs.clock_master_update_pb2 import ClockMasterUpdate
from sync_tooling_msgs.port_state_pb2 import PortState
from sync_tooling_msgs.port_state_update_pb2 import PortStateUpdate

from .util import (
    _gu,
    aggregated_status_label,
    graph_after_updates,
    make_measurement,
    make_phc2sys_link,
)


@pytest.mark.parametrize("clock_setup", ["plain", "ok_port", "faulty_port"])
def test_single_clock(nic_port, clock_setup):
    """
    A single clock by itself shall always be `Ok`, even if it has faulty ports.
    """

    clock_id = nic_port.clock_id

    match clock_setup:
        case "plain":
            u = _gu(ClockMasterUpdate(clock_id=clock_id))
        case "ok_port":
            u = _gu(PortStateUpdate(port_id=nic_port, port_state=PortState.PS_MASTER))
        case "faulty_port":
            u = _gu(PortStateUpdate(port_id=nic_port, port_state=PortState.PS_FAULTY))
        case _:
            raise AssertionError()

    g = graph_after_updates(u)

    assert clock_id in g._graph.nodes
    diag_tree = g.diagnose_clock(clock_id)
    assert aggregated_status_label(diag_tree) == "ok"


def test_cycle(sample_clock, remote_clock, nic_clock):
    """
    All clocks in a cycle shall be diagnosed as `Error`, clocks not in the cycle shall be unaffected.
    """

    cycle_clock_1 = sample_clock
    cycle_clock_2 = nic_clock
    unaffected_clock = remote_clock

    us = [
        make_phc2sys_link(cycle_clock_1, cycle_clock_2, False),
        make_phc2sys_link(cycle_clock_2, cycle_clock_1, False),
        make_measurement(cycle_clock_1, unaffected_clock, False),
    ]

    g = graph_after_updates(*us)

    for cycle_clock in (cycle_clock_1, cycle_clock_2):
        assert aggregated_status_label(g.diagnose_clock(cycle_clock)) == "error"

    assert aggregated_status_label(g.diagnose_clock(unaffected_clock)) == "ok"
