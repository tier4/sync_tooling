from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable, Literal

import networkx as nx

from sync_tooling_msgs.clock_alias_update_pb2 import ClockAliasUpdate
from sync_tooling_msgs.clock_diff_measurement_pb2 import ClockDiffMeasurement
from sync_tooling_msgs.clock_id_pb2 import ClockId
from sync_tooling_msgs.clock_master_update_pb2 import ClockMasterUpdate
from sync_tooling_msgs.diag_tree import Diagnosable, to_diag_tree
from sync_tooling_msgs.diag_tree_pb2 import DiagTree
from sync_tooling_msgs.graph_update_pb2 import GraphUpdate
from sync_tooling_msgs.phc2sys_status_message_pb2 import Phc2SysStatusMessage
from sync_tooling_msgs.phc2sys_update_pb2 import Phc2SysUpdate
from sync_tooling_msgs.port_id_pb2 import PortId
from sync_tooling_msgs.port_state import diagnose_port_state
from sync_tooling_msgs.port_state_update_pb2 import PortStateUpdate
from sync_tooling_msgs.ptp4l_port_status_message_pb2 import Ptp4lPortStatusMessage
from sync_tooling_msgs.ptp4l_status_message_pb2 import Ptp4lStatusMessage
from sync_tooling_msgs.ptp_parent_update_pb2 import PtpParentUpdate
from sync_tooling_msgs.servo_state import diagnose_servo_state
from sync_tooling_msgs.slave_clock_state_pb2 import SlaveClockState
from sync_tooling_msgs.unknown_pb2 import Unknown


def readability_score(clock_id: ClockId):
    match clock_id.WhichOneof("id"):
        case "frame_id":
            return 4
        case "system_clock_id":
            return 3
        case "interface_id":
            return 2
        case "linux_clock_device_id":
            return 1
        case "ptp_clock_id":
            return 0
    raise ValueError()


def get_most_human_readable_alias(aliases: Iterable[ClockId]) -> ClockId:
    return max(aliases, key=readability_score)


C_MASTER = "master"
C_STATUS_MSG = "status_msg"
C_PORT_IDS = "port_ids"

L_METADATA = "metadata"
L_TIME_DIFF = "time_diff"
L_STATUS_MSG = "status_msg"

P_PORT_STATE = "port_state"
P_STATUS_MSG = "status_msg"


def _get_node_attr(
    g: nx.DiGraph, n: ClockId, k: Literal["master", "status_msg", "port_ids"]
):
    return g.nodes[n].get(k)


def _set_node_attr(
    g: nx.DiGraph, n: ClockId, k: Literal["master", "status_msg", "port_ids"], v
):
    g.nodes[n][k] = v


def _get_edge_attr(
    g: nx.DiGraph,
    e: tuple[ClockId, ClockId],
    k: Literal["metadata", "time_diff", "status_msg"],
):
    return g.edges[e].get(k)


def _set_edge_attr(
    g: nx.DiGraph,
    e: tuple[ClockId, ClockId],
    k: Literal["metadata", "time_diff", "status_msg"],
    v,
):
    nx.set_edge_attributes(g, {e: v}, k)


@dataclass
class SyncGraph(Diagnosable):
    _graph: nx.DiGraph = field(default_factory=nx.DiGraph)
    _known_aliases: dict[ClockId, set[ClockId]] = field(default_factory=dict)
    _ports: defaultdict[PortId, dict[str, Any]] = field(
        default_factory=lambda: defaultdict(dict)
    )

    def get_canonical_clock_id(self, clock_id: ClockId) -> ClockId:
        if clock_id not in self._known_aliases:
            return clock_id
        return get_most_human_readable_alias(self._known_aliases[clock_id])

    def get_canonical_port_id(self, port_id: PortId):
        return PortId(
            clock_id=self.get_canonical_clock_id(port_id.clock_id),
            port_number=port_id.port_number,
            ptp_domain=port_id.ptp_domain,
        )

    def get_or_create_clock(self, clock_id: ClockId) -> ClockId:
        clock_id = self.get_canonical_clock_id(clock_id)
        if clock_id not in self._graph:
            self._graph.add_node(clock_id)
        assert clock_id in self._graph
        return clock_id

    def get_or_create_port(self, port_id: PortId) -> PortId:
        clock_id = self.get_or_create_clock(port_id.clock_id)
        port_id = self.get_canonical_port_id(port_id)

        updated_port_ids = {
            self.get_canonical_port_id(p)
            for p in _get_node_attr(self._graph, clock_id, C_PORT_IDS) or set()  # type: ignore
        }
        updated_port_ids.add(port_id)
        _set_node_attr(self._graph, clock_id, "port_ids", updated_port_ids)

        return port_id

    def update(self, update: GraphUpdate):
        match update.WhichOneof("update"):
            case "clock_alias_update":
                return self.update_clock_aliases(update.clock_alias_update)
            case "clock_master_update":
                return self.update_clock_master(update.clock_master_update)
            case "ptp_parent_update":
                return self.create_ptp_link(update.ptp_parent_update)
            case "port_state_update":
                return self.update_ptp_port_state(update.port_state_update)
            case "clock_diff_measurement":
                return self.handle_clock_diff_measurement(update.clock_diff_measurement)
            case "ptp4l_port_status_msg":
                return self.handle_ptp4l_port_status_message(
                    update.ptp4l_port_status_msg
                )
            case "ptp4l_status_msg":
                return self.handle_ptp4l_status_message(update.ptp4l_status_msg)
            case "phc2sys_status_msg":
                return self.handle_phc2sys_status_message(update.phc2sys_status_msg)
            case "phc2sys_update":
                return self.update_phc2sys_link_state(update.phc2sys_update)
        raise ValueError()

    def update_clock_master(self, u: ClockMasterUpdate):
        clock_id = self.get_or_create_clock(u.clock_id)
        _set_node_attr(
            self._graph, clock_id, "master", self.get_or_create_clock(u.master)
        )

    def update_clock_aliases(self, u: ClockAliasUpdate):
        if not u.aliases:
            return

        aliases_already_known = set()
        for alias in u.aliases:
            if alias in self._known_aliases:
                aliases_already_known |= self._known_aliases[alias]

        aliases_from_update = set(u.aliases).copy()

        if all(a in aliases_already_known for a in aliases_from_update):
            return

        all_aliases = aliases_already_known | aliases_from_update

        for alias in all_aliases:
            self._known_aliases[alias] = all_aliases

        canonical_id: ClockId = self.get_or_create_clock(next(iter(all_aliases)))
        datasets_to_combine = [
            self._graph.nodes[c] for c in all_aliases if c in self._graph
        ]
        combined_port_ids = {
            self.get_canonical_port_id(p)
            for dataset in datasets_to_combine
            for p in dataset.get(C_PORT_IDS, set())  # type: ignore
        }
        combined_status_msg = None
        combined_master = None

        relabelings = {alias: canonical_id for alias in all_aliases}
        self._graph = nx.relabel_nodes(self._graph, relabelings)

        _set_node_attr(self._graph, canonical_id, C_PORT_IDS, combined_port_ids)
        _set_node_attr(self._graph, canonical_id, C_STATUS_MSG, combined_status_msg)
        _set_node_attr(self._graph, canonical_id, C_MASTER, combined_master)

        for _, data in self._graph.nodes(True):
            if C_MASTER in data:
                data[C_MASTER] = self.get_canonical_clock_id(data[C_MASTER])
            if C_PORT_IDS in data:
                data[C_PORT_IDS] = {  # type: ignore
                    self.get_canonical_port_id(p)
                    for p in data[C_PORT_IDS]  # type: ignore
                }

        old_items = self._ports.items()
        self._ports.clear()
        for port_id, metadata in old_items:
            canonical_port_id = self.get_canonical_port_id(port_id)
            self._ports[canonical_port_id] = metadata

    def create_ptp_link(self, u: PtpParentUpdate):
        parent_port = self.get_or_create_port(u.parent)
        src_clock = parent_port.clock_id
        dst_clock = self.get_or_create_clock(u.clock_id)

        updated_port_ids = {
            self.get_canonical_port_id(p)
            for p in _get_node_attr(self._graph, src_clock, C_PORT_IDS) or set()
        }  # type: ignore
        updated_port_ids.add(parent_port)
        _set_node_attr(self._graph, src_clock, C_PORT_IDS, updated_port_ids)

        self._graph.add_edge(src_clock, dst_clock, **{L_METADATA: u.parent})

    def update_ptp_port_state(self, u: PortStateUpdate):
        canonical_id = self.get_or_create_port(u.port_id)

        if canonical_id not in self._ports:
            self._ports[canonical_id] = {}
        self._ports[canonical_id][P_PORT_STATE] = u.port_state

    def update_phc2sys_link_state(self, u: Phc2SysUpdate):
        src = self.get_or_create_clock(u.src)
        dst = self.get_or_create_clock(u.dst)
        key = (src, dst)
        if key not in self._graph.edges:
            self._graph.add_edge(*key)

        _set_edge_attr(self._graph, key, L_METADATA, u.clock_state)

    def handle_ptp4l_port_status_message(self, m: Ptp4lPortStatusMessage):
        pass

    def handle_ptp4l_status_message(self, m: Ptp4lStatusMessage):
        pass

    def handle_phc2sys_status_message(self, m: Phc2SysStatusMessage):
        pass

    def handle_clock_diff_measurement(self, m: ClockDiffMeasurement):
        pass

    def get_link(self, src: ClockId, dst: ClockId) -> SlaveClockState | PortId:
        src = self.get_canonical_clock_id(src)
        dst = self.get_canonical_clock_id(dst)
        return _get_edge_attr(self._graph, (src, dst), L_METADATA)

    def get_master(self, clock_id: ClockId) -> ClockId | None:
        clock_id = self.get_canonical_clock_id(clock_id)
        return _get_node_attr(self._graph, clock_id, C_MASTER)

    def get_ports(self, clock_id: ClockId) -> set[PortId]:
        clock_id = self.get_canonical_clock_id(clock_id)
        return _get_node_attr(self._graph, clock_id, C_PORT_IDS) or set()

    def get_sorted_aliases(self, clock_id: ClockId) -> list[ClockId]:
        if clock_id not in self._known_aliases:
            return [clock_id]

        aliases = self._known_aliases[clock_id]
        return sorted(aliases, key=readability_score, reverse=True)

    def diagnose_port(self, port_id: PortId) -> DiagTree:
        canonical_port_id = self.get_canonical_port_id(port_id)
        port_data = self._ports.get(canonical_port_id, None)
        unknown = to_diag_tree(Unknown(msg="Port state unknown"))

        if port_data is None:
            return unknown
        port_state = port_data.get(P_PORT_STATE)
        if port_state is None:
            return unknown
        return diagnose_port_state(port_state)

    def diagnose_link(self, src: ClockId, dst: ClockId) -> DiagTree:
        link = self.get_link(src, dst)
        match link:
            case PortId() as parent_port:
                return self.diagnose_port(parent_port)
            case SlaveClockState() as clock_state:
                return diagnose_servo_state(clock_state.servo_state)
        raise ValueError()

    def diagnose_clock(self, clock_id: ClockId) -> DiagTree:
        ports = self.get_ports(clock_id)

        return DiagTree(
            list=DiagTree.DiagList(list=[self.diagnose_port(p) for p in ports])
        )

    # def _diagnose_reachability(self) -> DiagStatus:
    #     if nx.is_weakly_connected(self._graph):
    #         return DiagStatus(ok=Ok())
    #     return DiagStatus(
    #         error=Error(
    #             msg=f"There are {nx.number_weakly_connected_components(self._graph)} mutually unreachable subgraphs"
    #         )
    #     )

    # def _diagnose_loops(self) -> DiagStatus:
    #     if nx.is_directed_acyclic_graph(self._graph):
    #         return DiagStatus(ok=Ok())
    #     return DiagStatus(error=Error(msg="There are loops in the graph"))

    # def _diagnose_ptp_domain(self, ptp_domain: nx.DiGraph):
    #     master_clocks = {
    #         self.get_canonical_clock_id(clock.master_id).id()
    #         for _, clock in SyncGraph.iter_clocks(ptp_domain)
    #         if clock.master_id is not None
    #     }

    #     if len(master_clocks) != 1:
    #         return DiagStatus(
    #             error=Error(
    #                 msg=f"Not all clocks in the domain agree on the same master. "
    #                 f"{len(master_clocks)} master clocks reported: {', '.join(master_clocks)}"
    #             )
    #         )

    #     master = next(iter(master_clocks))

    #     if master not in ptp_domain:
    #         return DiagStatus(
    #             error=Error(
    #                 msg=f"The reported master clock {master} cannot be found in the PTP domain"
    #             )
    #         )

    #     master_reaches_whole_domain = all(
    #         nx.has_path(ptp_domain, master, dst)
    #         for dst, _ in SyncGraph.iter_clocks(ptp_domain)
    #     )

    #     if not master_reaches_whole_domain:
    #         return DiagStatus(
    #             error=Error(
    #                 msg="Not all clocks in the domain are reachable from the master"
    #             )
    #         )

    #     return DiagStatus(ok=Ok())

    # def _iter_ptp_domain_graphs(self):
    #     def is_ptp_edge(src, dst):
    #         link = self.get_link(src, dst)
    #         return isinstance(link, PtpSyncLink)

    #     ptp_only_graph: nx.DiGraph = nx.subgraph_view(
    #         self._graph, filter_edge=is_ptp_edge
    #     )  # type: ignore

    #     for ptp_domain_nodes in nx.connected_components(ptp_only_graph):
    #         ptp_domain: nx.DiGraph = ptp_only_graph.subgraph(ptp_domain_nodes)
    #         yield ptp_domain

    def diagnose(self) -> DiagTree:
        return DiagTree()
