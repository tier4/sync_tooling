from sync_graph import SyncGraph
from sync_tooling_msgs.clock_alias_update_pb2 import ClockAliasUpdate
from sync_tooling_msgs.clock_master_update_pb2 import ClockMasterUpdate
from sync_tooling_msgs.graph_update_pb2 import GraphUpdate
from sync_tooling_msgs.phc2sys_update_pb2 import Phc2SysUpdate
from sync_tooling_msgs.port_id_pb2 import PortId
from sync_tooling_msgs.ptp_parent_update_pb2 import PtpParentUpdate
from sync_tooling_msgs.slave_clock_state_pb2 import SlaveClockState


def graph_after_updates(*updates: GraphUpdate):
    g = SyncGraph()
    for u in updates:
        g.update(u)
    return g


def test_clock_creation(sample_clock_ids):
    u = GraphUpdate(
        clock_master_update=ClockMasterUpdate(clock_id=sample_clock_ids["system"])
    )
    g = graph_after_updates(u)

    assert g._graph.number_of_nodes() == 1
    assert g._graph.number_of_edges() == 0


def test_clock_aliases(sample_clock_ids):
    u1 = GraphUpdate(
        clock_master_update=ClockMasterUpdate(clock_id=sample_clock_ids["system"])
    )
    u2 = GraphUpdate(
        clock_master_update=ClockMasterUpdate(clock_id=sample_clock_ids["ptp"])
    )
    u3 = GraphUpdate(
        clock_alias_update=ClockAliasUpdate(
            aliases=[sample_clock_ids["ptp"], sample_clock_ids["system"]]
        )
    )
    g = graph_after_updates(u1, u2, u3)

    assert g._graph.number_of_nodes() == 1
    assert g._graph.number_of_edges() == 0


def test_alias_precedence(sample_clock_ids):
    updates: list[GraphUpdate] = [
        GraphUpdate(clock_master_update=ClockMasterUpdate(clock_id=v))
        for v in sample_clock_ids.values()
    ]
    updates.append(
        GraphUpdate(
            clock_alias_update=ClockAliasUpdate(aliases=list(sample_clock_ids.values()))
        )
    )
    g = graph_after_updates(*updates)

    assert g._graph.number_of_nodes() == 1
    assert g._graph.has_node(sample_clock_ids["sensor"])
    assert not any(
        g._graph.has_node(v) for k, v in sample_clock_ids.items() if k != "sensor"
    )


def test_ptp_link(sample_clock_ids, remote_clock_ids):
    src = sample_clock_ids["system"]
    dst = remote_clock_ids["ptp"]

    u = GraphUpdate(
        ptp_parent_update=PtpParentUpdate(
            clock_id=dst, parent=PortId(clock_id=src, port_number=1)
        )
    )
    g = graph_after_updates(u)

    assert g._graph.number_of_nodes() == 2
    assert g._graph.number_of_edges() == 1
    assert g._graph.has_node(src)
    assert g._graph.has_node(dst)
    assert g._graph.has_edge(src, dst)


def test_phc2sys_link(sample_clock_ids, nic_clock_ids):
    src = sample_clock_ids["system"]
    dst = nic_clock_ids["device"]
    u = GraphUpdate(
        phc2sys_update=Phc2SysUpdate(src=src, dst=dst, clock_state=SlaveClockState())
    )
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
        GraphUpdate(
            phc2sys_update=Phc2SysUpdate(
                src=src1, dst=dst1, clock_state=SlaveClockState()
            )
        ),
        GraphUpdate(
            ptp_parent_update=PtpParentUpdate(
                clock_id=dst2, parent=PortId(clock_id=src2, port_number=1)
            )
        ),
        GraphUpdate(clock_alias_update=ClockAliasUpdate(aliases=[src1, src2])),
    ]

    g = graph_after_updates(*updates)

    assert g._graph.number_of_nodes() == 3
    assert g._graph.number_of_edges() == 2

    # Alias system clock takes precedence over alias PTP, thus making src1 the replacement for src2
    assert g._graph.has_edge(src1, dst1)
    assert g._graph.has_edge(src1, dst2)
