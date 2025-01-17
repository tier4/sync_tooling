from collections import defaultdict
from dataclasses import dataclass, field

import networkx as nx

from diag_tree import DiagTree, Ok, Error, Diagnosable, Unknown, DiagStatus


@dataclass(frozen=True)
class FrameId:
    frame: str

    def id(self):
        return self.frame


@dataclass(frozen=True)
class PtpClockId:
    clock_identifier: str

    def id(self):
        return self.clock_identifier


@dataclass(frozen=True)
class InterfaceId:
    hostname: str
    interface_name: str

    def id(self):
        return f"{self.hostname}.{self.interface_name}"


@dataclass(frozen=True)
class SystemClockId:
    hostname: str

    def id(self):
        return f"{self.hostname}.CLOCK_REALTIME"


@dataclass(frozen=True)
class LinuxClockDeviceId:
    hostname: str
    clock_device_number: int

    def id(self):
        return f"{self.hostname}.ptp{self.clock_device_number}"


@dataclass(frozen=True)
class PtpPortId:
    clock_id: PtpClockId
    port_number: int

    def id(self):
        return f"{self.clock_id.id()}-{self.port_number}"


ClockId = FrameId | PtpClockId | InterfaceId | SystemClockId | LinuxClockDeviceId


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
class Clock:
    master_id: ClockId | None = None


@dataclass
class PtpSyncLink:
    src_port: PtpPortId
    dst_port: PtpPortId


@dataclass
class Phc2SysSyncLink:
    diagnostics: DiagTree = field(default_factory=Unknown)


SyncLink = PtpSyncLink | Phc2SysSyncLink


@dataclass
class ClockAliasUpdate:
    aliases: set[ClockId]


@dataclass
class ClockUpdate:
    clock_id: ClockId
    new_state: Clock


@dataclass
class PtpPortLinkUpdate:
    src: PtpPortId
    dst: PtpPortId


@dataclass
class PtpPortStateUpdate:
    port_id: PtpPortId
    new_state: DiagTree


@dataclass
class Phc2SysUpdate:
    src: ClockId
    dst: ClockId
    new_state: DiagTree


GraphUpdate = (
    ClockAliasUpdate
    | ClockUpdate
    | PtpPortLinkUpdate
    | PtpPortStateUpdate
    | Phc2SysUpdate
)


@dataclass
class SyncGraph(Diagnosable):
    _DATA_KEY = "DATA"

    _graph: nx.DiGraph = field(default_factory=nx.DiGraph)
    _known_aliases: dict[ClockId, set[ClockId]] = field(default_factory=dict)
    _port_diagnostics: defaultdict[PtpPortId, DiagTree] = field(
        default_factory=lambda: defaultdict(default_factory=Unknown)
    )  # type: ignore

    def get_canonical_id(self, clock_id: ClockId):
        if clock_id not in self._known_aliases:
            return clock_id
        return get_most_human_readable_alias(self._known_aliases[clock_id])

    def update(self, update: GraphUpdate):
        match update:
            case ClockAliasUpdate(aliases):
                self.update_clock_aliases(aliases)
            case ClockUpdate(clock_id, clock):
                self.update_clock(clock_id, clock)
            case PtpPortLinkUpdate(src, dst):
                self.create_ptp_link(src, dst)
            case PtpPortStateUpdate(port_id, state):
                self.update_ptp_port_state(port_id, state)
            case Phc2SysUpdate(src, dst, state):
                link = Phc2SysSyncLink(state)
                self.update_link(src, dst, link)

    def get_or_create_clock(self, clock_id: ClockId) -> ClockId:
        clock_id = self.get_canonical_id(clock_id)
        if clock_id not in self._graph:
            self._graph.add_node(clock_id)
        return clock_id

    def update_clock(self, clock_id: ClockId, clock: Clock):
        clock_id = self.get_canonical_id(clock_id)

        self._graph[clock_id][SyncGraph._DATA_KEY] = clock  # type: ignore

    def update_clock_aliases(self, aliases: set[ClockId]):
        if not aliases:
            return

        all_aliases = aliases.copy()
        for alias in aliases:
            if alias in self._known_aliases:
                all_aliases |= self._known_aliases[alias]

        for alias in all_aliases:
            self._known_aliases[alias] = all_aliases

        canonical_id: ClockId = self.get_canonical_id(next(iter(all_aliases)))
        relabelings = {alias: canonical_id for alias in all_aliases}
        self._graph = nx.relabel_nodes(self._graph, relabelings)

    def create_ptp_link(self, src: PtpPortId, dst: PtpPortId):
        src_clock = self.get_or_create_clock(src.clock_id)
        dst_clock = self.get_or_create_clock(dst.clock_id)

        ################################
        # Remove edges connected to dst
        ################################

        # A master (src) port can have multiple slaves (dst) ports, but a slave port can have at most one master.
        # Remove all pre-existing links from `dst` as it now is a slave

        def shall_remove(data: SyncLink):
            match data:
                case PtpSyncLink() as ptp_link:
                    return dst_clock in [ptp_link.src_port, ptp_link.dst_port]
                case _:
                    return False

        dst_incoming_edges = self._graph.in_edges(dst_clock, data=SyncGraph._DATA_KEY)  # type: ignore
        marked_for_removal = [
            (u, v) for (u, v, data) in dst_incoming_edges if shall_remove(data)
        ]

        for edge in marked_for_removal:
            self._graph.remove_edge(*edge)

        ################################
        # Add new edge from src_clock to dst_clock
        ################################

        ptp_link = PtpSyncLink(src, dst)
        self._graph.add_edge(src_clock, dst_clock, **{SyncGraph._DATA_KEY: ptp_link})

    def update_ptp_port_state(self, port_id: PtpPortId, state: DiagTree):
        self._port_diagnostics[port_id] = state

    def update_link(self, src: ClockId, dst: ClockId, link: SyncLink):
        src = self.get_or_create_clock(src)
        dst = self.get_or_create_clock(dst)
        key = (src, dst)
        if key not in self._graph.edges:
            self._graph.add_edge(*key)
        self._graph.edges[key][SyncGraph._DATA_KEY] = link

    def get_link(self, src: ClockId, dst: ClockId) -> SyncLink:
        src = self.get_canonical_id(src)
        dst = self.get_canonical_id(dst)
        return self._graph.edges[(src, dst)][SyncGraph._DATA_KEY]

    @classmethod
    def iter_clocks(cls, g: nx.DiGraph):
        for id, data in g.nodes.items():
            tup: tuple[ClockId, Clock] = (id, data[SyncGraph._DATA_KEY])
            yield tup

    @classmethod
    def iter_links(cls, g: nx.DiGraph):
        for (src, dst), data in g.edges.items():
            tup: tuple[tuple[ClockId, ClockId], SyncLink] = (
                (src, dst),
                data[SyncGraph._DATA_KEY],
            )
            yield tup

    def _diagnose_links(self) -> DiagTree:
        def diagnose_link(link: SyncLink):
            match link:
                case PtpSyncLink(src, dst):
                    return {
                        "src": self._port_diagnostics[src],
                        "dst": self._port_diagnostics[dst],
                    }
                case Phc2SysSyncLink(diag):
                    return diag

        return {
            f"{src.id()} =({link.__class__.__name__})=> {dst.id()}": diagnose_link(link)
            for (src, dst), link in SyncGraph.iter_links(self._graph)
        }

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
            self.get_canonical_id(clock.master_id).id()
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
