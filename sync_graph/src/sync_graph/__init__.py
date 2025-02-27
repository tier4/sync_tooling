from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable

import networkx as nx

from diag_tree import Diagnosable
from sync_tooling_msgs.clock_alias_update_pb2 import ClockAliasUpdate
from sync_tooling_msgs.clock_diff_measurement_pb2 import ClockDiffMeasurement
from sync_tooling_msgs.clock_id import ClockKey, readable_clock_id
from sync_tooling_msgs.port_id import PortKey, readable_port_id
from sync_tooling_msgs.clock_id_pb2 import ClockId
from sync_tooling_msgs.clock_master_update_pb2 import ClockMasterUpdate
from sync_tooling_msgs.diag_tree_pb2 import DiagTree
from sync_tooling_msgs.graph_update_pb2 import GraphUpdate
from sync_tooling_msgs.phc2sys_update_pb2 import Phc2SysUpdate
from sync_tooling_msgs.port_id_pb2 import PortId
from sync_tooling_msgs.port_state_update_pb2 import PortStateUpdate
from sync_tooling_msgs.ptp_parent_update_pb2 import PtpParentUpdate
from sync_tooling_msgs.ptp4l_status_message_pb2 import Ptp4lStatusMessage
from sync_tooling_msgs.ptp4l_port_status_message_pb2 import Ptp4lPortStatusMessage
from sync_tooling_msgs.phc2sys_status_message_pb2 import Phc2SysStatusMessage


def get_most_human_readable_alias(aliases: Iterable[ClockId]) -> ClockId:
    def precedence(clock_id: ClockId):
        match clock_id.WhichOneof("id"):
            case "frame_id":
                return 0
            case "system_clock_id":
                return 1
            case "interface_id":
                return 2
            case "linux_clock_device_id":
                return 3
            case "ptp_clock_id":
                return 4
        raise ValueError()

    return min(aliases, key=precedence)


C_MASTER = "master"
C_STATUS_MSG = "status_msg"

L_METADATA = "metadata"
L_TIME_DIFF = "time_diff"
L_STATUS_MSG = "status_msg"

P_PORT_ID = "port_id"
P_DIAG = "diag"
P_STATUS_MSG = "status_msg"


@dataclass
class SyncGraph(Diagnosable):
    _graph: nx.DiGraph = field(default_factory=nx.DiGraph)
    _known_aliases: dict[ClockKey, list[ClockId]] = field(default_factory=dict)
    _ports: defaultdict[PortKey, dict[str, Any]] = field(
        default_factory=lambda: defaultdict(default_factory=dict)
    )  # type: ignore

    def get_canonical_clock_id(self, clock_id: ClockId) -> ClockId:
        readable_id = readable_clock_id(clock_id)
        if readable_id not in self._known_aliases:
            return clock_id
        return get_most_human_readable_alias(self._known_aliases[readable_id])

    def get_canonical_port_id(self, port_id: PortId):
        return PortId(
            clock_id=self.get_canonical_clock_id(port_id.clock_id),
            port_number=port_id.port_number,
            ptp_domain=port_id.ptp_domain,
        )

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

    def get_or_create_clock(self, clock_id: ClockId) -> ClockId:
        clock_id = self.get_canonical_clock_id(clock_id)
        if clock_id not in self._graph:
            self._graph.add_node(readable_clock_id(clock_id))
        return clock_id

    def update_clock_master(self, u: ClockMasterUpdate):
        clock_id = self.get_or_create_clock(u.clock_id)
        nx.set_node_attributes(
            self._graph, {readable_clock_id(clock_id): u.master}, C_MASTER
        )

    def update_clock_aliases(self, u: ClockAliasUpdate):
        if not u.aliases:
            return

        all_aliases = list(u.aliases).copy()
        for alias in u.aliases:
            readable_alias = readable_clock_id(alias)
            if readable_alias in self._known_aliases:
                all_aliases += self._known_aliases[readable_alias]

        for alias in all_aliases:
            readable_alias = readable_clock_id(alias)
            self._known_aliases[readable_alias] = all_aliases

        canonical_id: ClockId = self.get_canonical_clock_id(next(iter(all_aliases)))
        relabelings = {
            readable_clock_id(alias): readable_clock_id(canonical_id)
            for alias in all_aliases
        }
        self._graph = nx.relabel_nodes(self._graph, relabelings)

        old_items = self._ports.items()
        self._ports.clear()
        for _, metadata in old_items:
            port_id = metadata[P_PORT_ID]
            canonical_port_id = self.get_canonical_port_id(port_id)
            self._ports[readable_port_id(canonical_port_id)] = metadata

    def create_ptp_link(self, u: PtpParentUpdate):
        src_clock = self.get_or_create_clock(u.parent.clock_id)
        dst_clock = self.get_or_create_clock(u.clock_id)
        self._graph.add_edge(
            readable_clock_id(src_clock),
            readable_clock_id(dst_clock),
            **{L_METADATA: u.parent},
        )

    def update_ptp_port_state(self, u: PortStateUpdate):
        canonical_id = self.get_canonical_port_id(u.port_id)
        readable_id = readable_port_id(canonical_id)

        if readable_id not in self._ports:
            self._ports[readable_id] = {}
        self._ports[readable_id][P_PORT_ID] = canonical_id
        self._ports[readable_id][P_DIAG] = u.port_state

    def update_phc2sys_link_state(self, u: Phc2SysUpdate):
        src = self.get_or_create_clock(u.src)
        dst = self.get_or_create_clock(u.dst)
        key = (readable_clock_id(src), readable_clock_id(dst))
        if key not in self._graph.edges:
            self._graph.add_edge(*key)
        nx.set_edge_attributes(self._graph, {key: u.diag}, L_METADATA)

    def handle_ptp4l_port_status_message(self, m: Ptp4lPortStatusMessage):
        pass

    def handle_ptp4l_status_message(self, m: Ptp4lStatusMessage):
        pass

    def handle_phc2sys_status_message(self, m: Phc2SysStatusMessage):
        pass

    def handle_clock_diff_measurement(self, m: ClockDiffMeasurement):
        pass

    def get_link(self, src: ClockId, dst: ClockId) -> DiagTree | PortId:
        src = self.get_canonical_clock_id(src)
        dst = self.get_canonical_clock_id(dst)
        return self._graph.edges[(src, dst)][L_METADATA]

    def diagnose_link(self, src: ClockId, dst: ClockId) -> DiagTree:
        link = self.get_link(src, dst)
        match link:
            case PortId() as port_id:
                canonical_port_id = self.get_canonical_port_id(port_id)
                readable_id = readable_port_id(canonical_port_id)
                return self._ports[readable_id][P_DIAG]
            case DiagTree() as tree:
                return tree
        raise ValueError()

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
