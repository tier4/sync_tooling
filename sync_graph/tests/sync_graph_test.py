from diag_tree import Ok
from sync_graph import (
    Clock,
    ClockAliasUpdate,
    ClockUpdate,
    FrameId,
    GraphUpdate,
    InterfaceId,
    LinuxClockDeviceId,
    Phc2SysUpdate,
    PortId,
    PtpClockId,
    PtpPortLinkUpdate,
    SyncGraph,
    SystemClockId,
)

sample_clock = {
    "system": SystemClockId("sample"),
    "ptp": PtpClockId("012345.fffe.6789ab"),
    "frame": FrameId("my_frame"),
    "iface": InterfaceId("sample", "eno1"),
    "device": LinuxClockDeviceId("sample", 0),
}

nic_clock = {"device": LinuxClockDeviceId("sample", 3)}

remote_clock = {"ptp": PtpClockId("010101.fffe.101010")}


def graph_after_updates(*updates: GraphUpdate):
    g = SyncGraph()
    for u in updates:
        g.update(u)
    return g


def test_clock_creation():
    u = ClockUpdate(sample_clock["system"], Clock())
    g = graph_after_updates(u)

    assert g._graph.number_of_nodes() == 1
    assert g._graph.number_of_edges() == 0


def test_clock_aliases():
    u1 = ClockUpdate(sample_clock["system"], Clock())
    u2 = ClockUpdate(sample_clock["ptp"], Clock())
    u3 = ClockAliasUpdate({sample_clock["ptp"], sample_clock["system"]})
    g = graph_after_updates(u1, u2, u3)

    assert g._graph.number_of_nodes() == 1
    assert g._graph.number_of_edges() == 0


def test_alias_precedence():
    updates: list[GraphUpdate] = [
        ClockUpdate(v, Clock()) for v in sample_clock.values()
    ]
    updates.append(ClockAliasUpdate(set(sample_clock.values())))
    g = graph_after_updates(*updates)

    assert g._graph.number_of_nodes() == 1
    assert g._graph.has_node(sample_clock["frame"])
    assert not any(
        g._graph.has_node(v) for k, v in sample_clock.items() if k != "frame"
    )


def test_ptp_link():
    src = sample_clock["system"]
    dst = remote_clock["ptp"]

    u = PtpPortLinkUpdate(PortId(src, 1), PortId(dst, 1))
    g = graph_after_updates(u)

    assert g._graph.number_of_nodes() == 2
    assert g._graph.number_of_edges() == 1
    assert g._graph.has_node(src)
    assert g._graph.has_node(dst)
    assert g._graph.has_edge(src, dst)


def test_phc2sys_link():
    src = sample_clock["system"]
    dst = nic_clock["device"]
    u = Phc2SysUpdate(src, dst, Ok())
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
        Phc2SysUpdate(src1, dst1, Ok()),
        PtpPortLinkUpdate(PortId(src2, 1), PortId(dst2, 1)),
        ClockAliasUpdate({src1, src2}),
    ]

    g = graph_after_updates(*updates)

    assert g._graph.number_of_nodes() == 3
    assert g._graph.number_of_edges() == 2

    # Alias system clock takes precedence over alias PTP, thus making src1 the replacement for src2
    assert g._graph.has_edge(src1, dst1)
    assert g._graph.has_edge(src1, dst2)
