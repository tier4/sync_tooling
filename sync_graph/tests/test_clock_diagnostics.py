import pytest

from sync_tooling_msgs.clock_master_update_pb2 import ClockMasterUpdate
from sync_tooling_msgs.port_state_pb2 import PortState
from sync_tooling_msgs.port_state_update_pb2 import PortStateUpdate

from .util import _gu, aggregated_status_label, graph_after_updates


@pytest.mark.parametrize("clock_setup", ["plain", "ok_port", "faulty_port"])
def test_single_clock(nic_port_id, clock_setup):
    """
    A single clock by itself shall always be `Ok`, even if it has faulty ports.
    """

    clock_id = nic_port_id.clock_id

    match clock_setup:
        case "plain":
            u = _gu(ClockMasterUpdate(clock_id=clock_id))
        case "ok_port":
            u = _gu(
                PortStateUpdate(port_id=nic_port_id, port_state=PortState.PS_MASTER)
            )
        case "faulty_port":
            u = _gu(
                PortStateUpdate(port_id=nic_port_id, port_state=PortState.PS_FAULTY)
            )
        case _:
            raise AssertionError()

    g = graph_after_updates(u)

    assert clock_id in g._graph.nodes
    diag_tree = g.diagnose_clock(clock_id)
    assert aggregated_status_label(diag_tree) == "ok"
