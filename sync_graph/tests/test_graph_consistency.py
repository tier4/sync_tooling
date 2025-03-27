from sync_tooling_msgs.clock_alias_update_pb2 import ClockAliasUpdate
from sync_tooling_msgs.clock_master_update_pb2 import ClockMasterUpdate
from sync_tooling_msgs.graph_update_pb2 import GraphUpdate
from sync_tooling_msgs.phc2sys_update_pb2 import Phc2SysUpdate
from sync_tooling_msgs.port_id_pb2 import PortId
from sync_tooling_msgs.ptp_parent_update_pb2 import PtpParentUpdate
from sync_tooling_msgs.slave_clock_state_pb2 import SlaveClockState

from .util import _gu, graph_after_updates


def test_clock_creation(sample_clock_ids):
    u = _gu(ClockMasterUpdate(clock_id=sample_clock_ids["system"]))
    g = graph_after_updates(u)

    assert g._graph.number_of_nodes() == 1
    assert g._graph.number_of_edges() == 0


def test_clock_aliases(sample_clock_ids):
    u1 = _gu(ClockMasterUpdate(clock_id=sample_clock_ids["system"]))
    u2 = _gu(ClockMasterUpdate(clock_id=sample_clock_ids["ptp"]))
    u3 = _gu(
        ClockAliasUpdate(aliases=[sample_clock_ids["ptp"], sample_clock_ids["system"]])
    )
    g = graph_after_updates(u1, u2, u3)

    assert g._graph.number_of_nodes() == 1
    assert g._graph.number_of_edges() == 0


def test_alias_precedence(sample_clock_ids):
    updates: list[GraphUpdate] = [
        _gu(ClockMasterUpdate(clock_id=v)) for v in sample_clock_ids.values()
    ]
    updates.append(_gu(ClockAliasUpdate(aliases=list(sample_clock_ids.values()))))
    g = graph_after_updates(*updates)

    assert g._graph.number_of_nodes() == 1
    assert g._graph.has_node(sample_clock_ids["sensor"])


def test_ptp_link(sample_clock_ids, remote_clock_ids):
    src = sample_clock_ids["system"]
    dst = remote_clock_ids["ptp"]

    u = _gu(PtpParentUpdate(clock_id=dst, parent=PortId(clock_id=src, port_number=1)))
    g = graph_after_updates(u)

    assert g._graph.number_of_nodes() == 2
    assert g._graph.number_of_edges() == 1
    assert g._graph.has_node(src)
    assert g._graph.has_node(dst)
    assert g._graph.has_edge(src, dst)


def test_phc2sys_link(sample_clock_ids, nic_clock_ids):
    src = sample_clock_ids["system"]
    dst = nic_clock_ids["device"]
    u = _gu(Phc2SysUpdate(src=src, dst=dst, clock_state=SlaveClockState()))
    g = graph_after_updates(u)

    assert g._graph.number_of_nodes() == 2
    assert g._graph.number_of_edges() == 1
    assert g._graph.has_node(src)
    assert g._graph.has_node(dst)
    assert g._graph.has_edge(src, dst)


def test_alias_after_links(sample_clock_ids, nic_clock_ids, remote_clock_ids):
    src1 = sample_clock_ids["system"]
    dst1 = nic_clock_ids["device"]

    src2 = sample_clock_ids["ptp"]
    dst2 = remote_clock_ids["ptp"]

    updates = [
        _gu(Phc2SysUpdate(src=src1, dst=dst1, clock_state=SlaveClockState())),
        _gu(
            PtpParentUpdate(clock_id=dst2, parent=PortId(clock_id=src2, port_number=1))
        ),
        _gu(ClockAliasUpdate(aliases=[src1, src2])),
    ]

    g = graph_after_updates(*updates)

    assert g._graph.number_of_nodes() == 3
    assert g._graph.number_of_edges() == 2

    # Alias system clock takes precedence over alias PTP, thus making src1 the replacement for src2
    assert g._graph.has_edge(src1, dst1)
    assert g._graph.has_edge(src1, dst2)
