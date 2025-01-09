from dataclasses import dataclass
from typing import Literal

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
    master_id: ClockId


@dataclass
class SyncLink(Diagnosable):
    kind: Literal["PTP", "PHC2SYS"]
    diagnostics: DiagTree | None

    def diagnose(self) -> DiagTree:
        if self.diagnostics is None:
            return Unknown()

        return self.diagnostics


@dataclass
class DiagGraph(Diagnosable):
    _DATA_KEY = "DATA"

    _graph: nx.DiGraph
    _known_aliases: dict[ClockId, set[ClockId]] = {}

    def get_canonical_id(self, id: ClockId):
        if id not in self._known_aliases:
            return id
        return get_most_human_readable_alias(self._known_aliases[id])

    def update_clock(self, id: ClockId, clock: Clock):
        id = self.get_canonical_id(id)
        if id not in self._graph:
            self._graph.add_node(id)
        self._graph[id][DiagGraph._DATA_KEY] = clock  # type: ignore

    def update_clock_aliases(self, aliases: set[ClockId]):
        if not aliases:
            return

        all_aliases = aliases.copy()
        for alias in aliases:
            if alias in self._known_aliases:
                all_aliases |= self._known_aliases[alias]

        for alias in all_aliases:
            self._known_aliases[alias] = all_aliases

        alias = next(iter(all_aliases))
        canonical_id = self.get_canonical_id(alias)
        relabelings = {alias: canonical_id for alias in all_aliases}
        self._graph = nx.relabel_nodes(self._graph, relabelings)

    def update_link(self, src: ClockId, dst: ClockId, link: SyncLink):
        src = self.get_canonical_id(src)
        dst = self.get_canonical_id(dst)
        key = (src, dst)
        if key not in self._graph.edges:
            self._graph.add_edge(*key)
        self._graph.edges[key][DiagGraph._DATA_KEY] = link

    def get_clock(self, id: ClockId) -> Clock:
        id = self.get_canonical_id(id)
        return self._graph[id][DiagGraph._DATA_KEY]

    def get_link(self, src: ClockId, dst: ClockId) -> SyncLink:
        src = self.get_canonical_id(src)
        dst = self.get_canonical_id(dst)
        return self._graph.edges[(src, dst)][DiagGraph._DATA_KEY]

    @classmethod
    def iter_clocks(cls, g: nx.DiGraph):
        for id, data in g.nodes.items():
            tup: tuple[ClockId, Clock] = (id, data[DiagGraph._DATA_KEY])
            yield tup

    @classmethod
    def iter_links(cls, g: nx.DiGraph):
        for (src, dst), data in g.edges.items():
            tup: tuple[tuple[ClockId, ClockId], SyncLink] = (
                (src, dst),
                data[DiagGraph._DATA_KEY],
            )
            yield tup

    def _diagnose_links(self) -> DiagTree:
        return {
            f"{src.id()} =({link.kind})=> {dst.id()}": link.diagnose()
            for (src, dst), link in DiagGraph.iter_links(self._graph)
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
            for _, clock in DiagGraph.iter_clocks(ptp_domain)
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
            for dst, _ in DiagGraph.iter_clocks(ptp_domain)
        )

        if not master_reaches_whole_domain:
            return Error("Not all clocks in the domain are reachable from the master")

        return Ok()

    def _iter_ptp_domain_graphs(self):
        def is_ptp_edge(src, dst):
            link = self.get_link(src, dst)
            return link.kind == "PTP"

        ptp_only_graph: nx.DiGraph = nx.subgraph_view(
            self._graph, filter_edge=is_ptp_edge
        )  # type: ignore

        for ptp_domain_nodes in nx.connected_components(ptp_only_graph):
            ptp_domain: nx.DiGraph = ptp_only_graph.subgraph(ptp_domain_nodes)
            yield ptp_domain

    def diagnose(self) -> DiagTree:
        return {}
