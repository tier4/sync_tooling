from sync_graph import SyncGraph
from sync_tooling_msgs.clock_alias_update_pb2 import ClockAliasUpdate
from sync_tooling_msgs.clock_id_pb2 import ClockId
from sync_tooling_msgs.clock_master_update_pb2 import ClockMasterUpdate
from sync_tooling_msgs.frame_id_pb2 import FrameId
from sync_tooling_msgs.graph_update_pb2 import GraphUpdate
from sync_tooling_msgs.interface_id_pb2 import InterfaceId
from sync_tooling_msgs.linux_clock_device_id_pb2 import LinuxClockDeviceId
from sync_tooling_msgs.phc2sys_update_pb2 import Phc2SysUpdate
from sync_tooling_msgs.port_id_pb2 import PortId
from sync_tooling_msgs.ptp_clock_id_pb2 import PtpClockId
from sync_tooling_msgs.ptp_parent_update_pb2 import PtpParentUpdate
from sync_tooling_msgs.slave_clock_state_pb2 import SlaveClockState
from sync_tooling_msgs.system_clock_id_pb2 import SystemClockId

sample_clock = {
    "system": ClockId(system_clock_id=SystemClockId(hostname="sample")),
    "ptp": ClockId(ptp_clock_id=PtpClockId(id="012345.fffe.6789ab")),
    "frame": ClockId(frame_id=FrameId(frame="my_frame")),
    "iface": ClockId(
        interface_id=InterfaceId(hostname="sample", interface_name="eno1")
    ),
    "device": ClockId(
        linux_clock_device_id=LinuxClockDeviceId(
            hostname="sample", clock_device_number=0
        )
    ),
}

nic_clock = {
    "device": ClockId(
        linux_clock_device_id=LinuxClockDeviceId(
            hostname="sample", clock_device_number=3
        )
    )
}

remote_clock = {"ptp": ClockId(ptp_clock_id=PtpClockId(id="010101.fffe.101010"))}


def graph_after_updates(*updates: GraphUpdate):
    g = SyncGraph()
    for u in updates:
        g.update(u)
    return g


def test_clock_creation():
    u = GraphUpdate(
        clock_master_update=ClockMasterUpdate(
            clock_id=sample_clock["system"], master=None
        )
    )
    g = graph_after_updates(u)

    assert g._graph.number_of_nodes() == 1
    assert g._graph.number_of_edges() == 0


def test_clock_aliases():
    u1 = GraphUpdate(
        clock_master_update=ClockMasterUpdate(
            clock_id=sample_clock["system"], master=None
        )
    )
    u2 = GraphUpdate(
        clock_master_update=ClockMasterUpdate(clock_id=sample_clock["ptp"], master=None)
    )
    u3 = GraphUpdate(
        clock_alias_update=ClockAliasUpdate(
            aliases=[sample_clock["ptp"], sample_clock["system"]]
        )
    )
    g = graph_after_updates(u1, u2, u3)

    assert g._graph.number_of_nodes() == 1
    assert g._graph.number_of_edges() == 0


def test_alias_precedence():
    updates: list[GraphUpdate] = [
        GraphUpdate(clock_master_update=ClockMasterUpdate(clock_id=v, master=None))
        for v in sample_clock.values()
    ]
    updates.append(
        GraphUpdate(
            clock_alias_update=ClockAliasUpdate(aliases=list(sample_clock.values()))
        )
    )
    g = graph_after_updates(*updates)

    assert g._graph.number_of_nodes() == 1
    assert g._graph.has_node(sample_clock["frame"])
    assert not any(
        g._graph.has_node(v) for k, v in sample_clock.items() if k != "frame"
    )


def test_ptp_link():
    src = sample_clock["system"]
    dst = remote_clock["ptp"]

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


def test_phc2sys_link():
    src = sample_clock["system"]
    dst = nic_clock["device"]
    u = GraphUpdate(
        phc2sys_update=Phc2SysUpdate(src=src, dst=dst, clock_state=SlaveClockState())
    )
    g = graph_after_updates(u)

    assert g._graph.number_of_nodes() == 2
    assert g._graph.number_of_edges() == 1
    assert g._graph.has_node(src)
    assert g._graph.has_node(dst)
    assert g._graph.has_edge(src, dst)


def test_alias_after_links():
    src1 = sample_clock["system"]
    dst1 = nic_clock["device"]

    src2 = sample_clock["ptp"]
    dst2 = remote_clock["ptp"]

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
