from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import networkx as nx

from diag_tree import DiagTree, Ok, Error, Diagnosable, Unknown, DiagStatus


@dataclass(frozen=True)
class FrameId:
    frame: str

    def id(self):
        return self.frame

    def __str__(self) -> str:
        return self.id()


@dataclass(frozen=True)
class PtpClockId:
    clock_identifier: str

    def id(self):
        return self.clock_identifier

    def __str__(self) -> str:
        return self.id()


@dataclass(frozen=True)
class InterfaceId:
    hostname: str
    interface_name: str

    def id(self):
        return f"{self.hostname}.{self.interface_name}"

    def __str__(self) -> str:
        return self.id()


@dataclass(frozen=True)
class SystemClockId:
    hostname: str

    def id(self):
        return f"{self.hostname}.sys"

    def __str__(self) -> str:
        return self.id()


@dataclass(frozen=True)
class LinuxClockDeviceId:
    hostname: str
    clock_device_number: int

    def id(self):
        return f"{self.hostname}.ptp{self.clock_device_number}"

    def __str__(self) -> str:
        return self.id()


ClockId = FrameId | PtpClockId | InterfaceId | SystemClockId | LinuxClockDeviceId


@dataclass(frozen=True)
class PortId:
    clock_id: ClockId
    port_number: int
    domain_number: int

    def id(self):
        return f"{self.domain_number}:{self.clock_id.id()}-{self.port_number}"


def get_most_human_readable_alias(aliases: set[ClockId]) -> ClockId:
    readability_order = [
        FrameId,
        SystemClockId,
        InterfaceId,
        LinuxClockDeviceId,
        PtpClockId,
    ]
    return min(aliases, key=lambda id: readability_order.index(type(id)))


@dataclass
class PtpSyncLink:
    src_port: PortId

    def __str__(self) -> str:
        return f"PTP (master port: {self.src_port.port_number})"


@dataclass
class Phc2SysSyncLink:
    diagnostics: DiagTree = field(default_factory=Unknown)


SyncLink = PtpSyncLink | Phc2SysSyncLink


@dataclass
class ClockAliasUpdate:
    aliases: set[ClockId]


@dataclass
class TimeDifferenceMeasurement:
    class Type(Enum):
        Ptp4lReported = 0
        Phc2SysReported = 1
        PtpManagementReported = 2
        NebulaUdpDriver = 3
        NebulaApproximate = 4

    src: ClockId
    dst: ClockId
    diff_ns: int
    type: Type


@dataclass
class ClockMasterUpdate:
    clock_id: ClockId
    master: ClockId | None


@dataclass
class PtpParentUpdate:
    src: PortId
    dst: ClockId


@dataclass
class PtpPortStateUpdate:
    port_id: PortId
    new_state: DiagTree


@dataclass
class Ptp4lPortStatusMessage:
    port_id: PortId
    message: Warning | Error


@dataclass
class Ptp4lStatusMessage:
    clock_id: ClockId
    message: Warning | Error


@dataclass
class Phc2SysStatusMessage:
    dst_clocks: set[ClockId]
    message: Warning | Error


@dataclass
class Phc2SysUpdate:
    src: ClockId
    dst: ClockId
    new_state: DiagTree


GraphUpdate = (
    ClockAliasUpdate
    | TimeDifferenceMeasurement
    | ClockMasterUpdate
    | PtpParentUpdate
    | PtpPortStateUpdate
    | Ptp4lPortStatusMessage
    | Ptp4lStatusMessage
    | Phc2SysStatusMessage
    | Phc2SysUpdate
)

C_MASTER = "master"
C_STATUS_MSG = "status_msg"

L_METADATA = "metadata"
L_TIME_DIFF = "time_diff"
L_STATUS_MSG = "status_msg"

P_DIAG = "diag"
P_STATUS_MSG = "status_msg"


@dataclass
class SyncGraph(Diagnosable):
    _graph: nx.DiGraph = field(default_factory=nx.DiGraph)
    _known_aliases: dict[ClockId, set[ClockId]] = field(default_factory=dict)
    _ports: defaultdict[PortId, dict[str, Any]] = field(
        default_factory=lambda: defaultdict(default_factory=dict)
    )  # type: ignore

    def get_canonical_clock_id(self, clock_id: ClockId):
        if clock_id not in self._known_aliases:
            return clock_id
        return get_most_human_readable_alias(self._known_aliases[clock_id])

    def get_canonical_port_id(self, port_id: PortId):
        return PortId(
            self.get_canonical_clock_id(port_id.clock_id),
            port_id.port_number,
            port_id.domain_number,
        )

    def update(self, update: GraphUpdate):
        match update:
            case ClockAliasUpdate():
                self.update_clock_aliases(update)
            case ClockMasterUpdate():
                self.update_clock_master(update)
            case PtpParentUpdate():
                self.create_ptp_link(update)
            case PtpPortStateUpdate():
                self.update_ptp_port_state(update)
            case TimeDifferenceMeasurement():
                pass
            case Ptp4lPortStatusMessage():
                self.update_port_status_msg(update)
            case Ptp4lStatusMessage():
                self.update_ptp4l_status_msg(update)
            case Phc2SysStatusMessage():
                self.update_phc2sys_status_msg(update)
            case Phc2SysUpdate():
                self.update_link(
                    update.src, update.dst, Phc2SysSyncLink(update.new_state)
                )

    def get_or_create_clock(self, clock_id: ClockId) -> ClockId:
        clock_id = self.get_canonical_clock_id(clock_id)
        if clock_id not in self._graph:
            self._graph.add_node(clock_id)
        return clock_id

    def update_clock_master(self, u: ClockMasterUpdate):
        clock_id = self.get_or_create_clock(u.clock_id)
        nx.set_node_attributes(self._graph, {clock_id: u.master}, C_MASTER)

    def update_clock_aliases(self, u: ClockAliasUpdate):
        if not u.aliases:
            return

        all_aliases = set(u.aliases).copy()
        for alias in u.aliases:
            if alias in self._known_aliases:
                all_aliases |= self._known_aliases[alias]

        for alias in all_aliases:
            self._known_aliases[alias] = all_aliases

        canonical_id: ClockId = self.get_canonical_clock_id(next(iter(all_aliases)))
        relabelings = {alias: canonical_id for alias in all_aliases}
        self._graph = nx.relabel_nodes(self._graph, relabelings)

        old_items = self._ports.items()
        self._ports.clear()
        self._ports.update({self.get_canonical_port_id(p): d for p, d in old_items})

    def create_ptp_link(self, u: PtpParentUpdate):
        src_clock = self.get_or_create_clock(u.src.clock_id)
        dst_clock = self.get_or_create_clock(u.dst)

        ptp_link = PtpSyncLink(u.src)
        self._graph.add_edge(src_clock, dst_clock, **{L_METADATA: ptp_link})

    def update_ptp_port_state(self, u: PtpPortStateUpdate):
        self._ports[u.port_id][P_DIAG] = u.new_state

    def update_link(self, src: ClockId, dst: ClockId, link: SyncLink):
        src = self.get_or_create_clock(src)
        dst = self.get_or_create_clock(dst)
        key = (src, dst)
        if key not in self._graph.edges:
            self._graph.add_edge(*key)
        nx.set_edge_attributes(self._graph, {key: link}, L_METADATA)

    def get_link(self, src: ClockId, dst: ClockId) -> SyncLink:
        src = self.get_canonical_clock_id(src)
        dst = self.get_canonical_clock_id(dst)
        return self._graph.edges[(src, dst)][L_METADATA]

    def _diagnose_reachability(self) -> DiagStatus:
        if nx.is_weakly_connected(self._graph):
            return Ok()
        return Error(
            f"There are {nx.number_weakly_connected_components(self._graph)} mutually unreachable subgraphs"
        )

    def _diagnose_loops(self) -> DiagStatus:
        if nx.is_directed_acyclic_graph(self._graph):
            return Ok()
        return Error("There are loops in the graph")

    def _diagnose_ptp_domain(self, ptp_domain: nx.DiGraph):
        master_clocks = {
            self.get_canonical_clock_id(clock.master_id).id()
            for _, clock in SyncGraph.iter_clocks(ptp_domain)
            if clock.master_id is not None
        }

        if len(master_clocks) != 1:
            return Error(
                f"Not all clocks in the domain agree on the same master. "
                f"{len(master_clocks)} master clocks reported: {', '.join(master_clocks)}"
            )

        master = next(iter(master_clocks))

        if master not in ptp_domain:
            return Error(
                f"The reported master clock {master} cannot be found in the PTP domain"
            )

        master_reaches_whole_domain = all(
            nx.has_path(ptp_domain, master, dst)
            for dst, _ in SyncGraph.iter_clocks(ptp_domain)
        )

        if not master_reaches_whole_domain:
            return Error("Not all clocks in the domain are reachable from the master")

        return Ok()

    def _iter_ptp_domain_graphs(self):
        def is_ptp_edge(src, dst):
            link = self.get_link(src, dst)
            return isinstance(link, PtpSyncLink)

        ptp_only_graph: nx.DiGraph = nx.subgraph_view(
            self._graph, filter_edge=is_ptp_edge
        )  # type: ignore

        for ptp_domain_nodes in nx.connected_components(ptp_only_graph):
            ptp_domain: nx.DiGraph = ptp_only_graph.subgraph(ptp_domain_nodes)
            yield ptp_domain

    def diagnose(self) -> DiagTree:
        return {}
