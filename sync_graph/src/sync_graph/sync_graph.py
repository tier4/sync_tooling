from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable, Literal

import networkx as nx

from sync_tooling_msgs.clock_alias_update_pb2 import ClockAliasUpdate
from sync_tooling_msgs.clock_diff_measurement_pb2 import ClockDiffMeasurement
from sync_tooling_msgs.clock_id import readable_clock_id
from sync_tooling_msgs.clock_id_pb2 import ClockId
from sync_tooling_msgs.clock_master_update_pb2 import ClockMasterUpdate
from sync_tooling_msgs.diag_status_pb2 import DiagStatus
from sync_tooling_msgs.diag_tree import aggregate, to_diag_tree
from sync_tooling_msgs.diag_tree_pb2 import DiagTree
from sync_tooling_msgs.error_pb2 import Error
from sync_tooling_msgs.graph_update_pb2 import GraphUpdate
from sync_tooling_msgs.ok_pb2 import Ok
from sync_tooling_msgs.phc2sys_status_message_pb2 import Phc2SysStatusMessage
from sync_tooling_msgs.phc2sys_update_pb2 import Phc2SysUpdate
from sync_tooling_msgs.port_id_pb2 import PortId
from sync_tooling_msgs.port_state import diagnose_port_state
from sync_tooling_msgs.port_state_update_pb2 import PortStateUpdate
from sync_tooling_msgs.ptp4l_port_status_message_pb2 import Ptp4lPortStatusMessage
from sync_tooling_msgs.ptp4l_status_message_pb2 import Ptp4lStatusMessage
from sync_tooling_msgs.ptp_parent_update_pb2 import PtpParentUpdate
from sync_tooling_msgs.self_reported_clock_state import diagnose_clock_state
from sync_tooling_msgs.self_reported_clock_state_update_pb2 import (
    SelfReportedClockStateUpdate,
)
from sync_tooling_msgs.servo_state import diagnose_servo_state
from sync_tooling_msgs.slave_clock_state_pb2 import SlaveClockState
from sync_tooling_msgs.unknown_pb2 import Unknown
from sync_tooling_msgs.warning_pb2 import Warning


def readability_score(clock_id: ClockId):
    match clock_id.WhichOneof("id"):
        case "sensor_id":
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


def diagnose_clock_diff(time_diff_ns: int):
    time_diff_us = time_diff_ns // 1000
    warn_threshold_us = 500
    error_threshold_us = 2_000

    if time_diff_us > error_threshold_us:
        return to_diag_tree(Error(msg=f"Exceeds bounds of {error_threshold_us} µs"))
    if time_diff_us > warn_threshold_us:
        return to_diag_tree(Warning(msg=f"Exceeds bounds of {warn_threshold_us} µs"))

    return to_diag_tree(Ok(msg=f"Within bounds of {warn_threshold_us} µs"))


C_STATUS_MSG = "status_msg"
C_PORT_IDS = "port_ids"
C_SELF_REPORTED_STATE = "self_reported_state"
METADATA = "metadata"

L_MASTER = "master"
L_PTP_PARENT = "ptp_parent"
L_MEASUREMENT = "measurement"
L_PHC2SYS = "phc2sys"

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


@dataclass
class SyncGraph:
    reference_graph: nx.DiGraph | None = None

    _graph: nx.MultiDiGraph = field(default_factory=nx.MultiDiGraph)
    _known_aliases: dict[ClockId, set[ClockId]] = field(default_factory=dict)
    _ports: defaultdict[PortId, dict[str, Any]] = field(
        default_factory=lambda: defaultdict(dict)
    )

    def get_canonical_clock_id(self, clock_id: ClockId) -> ClockId:
        assert clock_id is not None
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

    def update(self, update: GraphUpdate):  # noqa: C901
        """
        Apply `update` to the sync graph.

        Graph consistency is ensured:

        - for an invalid update, nothing changes
        - for an update referencing new clocks, the clocks are added to the graph
        - for clock alias updates, references to all aliases are updated to the (new) canonical alias

        Args:
            update: The update to apply. The `update` field has to be set.

        Raises:
            ValueError: If the `update` field is unset or set to an unsupported update type.
        """
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
            case "self_reported_clock_state_update":
                return self.update_self_reported_clock_state(
                    update.self_reported_clock_state_update
                )
            case None:
                # Invalid graph update, ignore
                return

        raise AssertionError(f"Unknown update type: {update.WhichOneof('update')}")

    def update_clock_master(self, u: ClockMasterUpdate):
        if not u.HasField("clock_id"):
            return

        clock_id = self.get_or_create_clock(u.clock_id)
        if not u.HasField("master"):
            outdated_edges = [
                (src, clock_id, key)
                for src, _, key in self._graph.in_edges(clock_id, keys=True)
                if key == L_MASTER
            ]

            self._graph.remove_edges_from(outdated_edges)
            return

        master_id = self.get_or_create_clock(u.master)

        # Do not introduce self-loops
        if master_id == clock_id:
            return

        self._graph.add_edge(
            master_id, clock_id, L_MASTER, **{METADATA: u.master_offset_ns}
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

        relabelings = dict.fromkeys(all_aliases, canonical_id)
        self._graph = nx.relabel_nodes(self._graph, relabelings)

        # Remove potential self-loops resulting from combining nodes
        # edges(canonical_id) returns all edges connected to canonical_id, want to only remove the ones that are self-loops
        edges_to_remove = [
            (src, dst, key)
            for src, dst, key in self._graph.edges(canonical_id, keys=True)
            if src == canonical_id and dst == canonical_id
        ]
        self._graph.remove_edges_from(edges_to_remove)

        _set_node_attr(self._graph, canonical_id, C_PORT_IDS, combined_port_ids)
        _set_node_attr(self._graph, canonical_id, C_STATUS_MSG, combined_status_msg)

        for _, data in self._graph.nodes(True):
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
        if not u.HasField("clock_id"):
            return

        dst_clock = self.get_or_create_clock(u.clock_id)
        if not u.HasField("parent"):
            outdated_edges = [
                (src, dst_clock, key)
                for src, _, key in self._graph.in_edges(dst_clock, keys=True)
                if key == L_PTP_PARENT
            ]

            self._graph.remove_edges_from(outdated_edges)
            return

        # Port number 0 is reserved for internal PTP mechanisms, discard it
        if u.parent.port_number == 0:
            return

        parent_port = self.get_or_create_port(u.parent)
        src_clock = self.get_or_create_clock(parent_port.clock_id)

        # Do not introduce self-loops
        if src_clock == dst_clock:
            return

        updated_port_ids = {
            self.get_canonical_port_id(p)
            for p in _get_node_attr(self._graph, src_clock, C_PORT_IDS) or set()  # type: ignore
        }  # type: ignore

        updated_port_ids.add(parent_port)
        _set_node_attr(self._graph, src_clock, C_PORT_IDS, updated_port_ids)

        self._graph.add_edge(
            src_clock, dst_clock, L_PTP_PARENT, **{METADATA: parent_port}
        )

    def update_ptp_port_state(self, u: PortStateUpdate):
        # Port 0 is reserved for internal PTP instance mechanisms.
        # Keeping track of it has no particular use, so discard it
        if u.port_id.port_number == 0:
            return

        canonical_id = self.get_or_create_port(u.port_id)

        if canonical_id not in self._ports:
            self._ports[canonical_id] = {}
        self._ports[canonical_id][P_PORT_STATE] = u.port_state

    def update_phc2sys_link_state(self, u: Phc2SysUpdate):
        if not u.HasField("dst"):
            return

        dst = self.get_or_create_clock(u.dst)
        if not u.HasField("src"):
            outdated_edges = [
                (src, dst, key)
                for src, _, key in self._graph.in_edges(dst, keys=True)
                if key == L_PHC2SYS
            ]
            self._graph.remove_edges_from(outdated_edges)
            return

        src = self.get_or_create_clock(u.src)

        # Do not introduce self-loops
        if src == dst:
            return

        self._graph.add_edge(src, dst, L_PHC2SYS, **{METADATA: u.clock_state})

    def update_self_reported_clock_state(self, u: SelfReportedClockStateUpdate):
        if not u.HasField("clock_id"):
            return

        if u.state == SelfReportedClockStateUpdate.State.INVALID:
            return

        clock_id = self.get_or_create_clock(u.clock_id)
        self._graph.nodes[clock_id][C_SELF_REPORTED_STATE] = u.state

    def handle_ptp4l_port_status_message(self, m: Ptp4lPortStatusMessage):
        pass

    def handle_ptp4l_status_message(self, m: Ptp4lStatusMessage):
        pass

    def handle_phc2sys_status_message(self, m: Phc2SysStatusMessage):
        pass

    def handle_clock_diff_measurement(self, m: ClockDiffMeasurement):
        if not m.HasField("src") or not m.HasField("dst"):
            return

        src = self.get_or_create_clock(m.src)
        dst = self.get_or_create_clock(m.dst)

        # Do not introduce self-loops
        if src == dst:
            return

        self._graph.add_edge(src, dst, L_MEASUREMENT, **{METADATA: m.diff_ns})

    def get_links(
        self, src: ClockId, dst: ClockId
    ) -> list[
        tuple[Literal["master"], int]
        | tuple[Literal["measurement"], int]
        | tuple[Literal["ptp_parent"], PortId]
        | tuple[Literal["phc2sys"], SlaveClockState]
    ]:
        """
        Get all links between `src` and `dst`.

        There are multiple link types, and up to one of each can exist at the same time:

        - PHC2SYS, with the current slave clock state
        - PTP (parent), with the PTP parent port ID
        - PTP (master), with the master offset in nanoseconds
        - Measurement, with the `src` to `dst` offset measurement in nanoseconds

        Args:
            src: The source clock. Has to be valid and in the graph.
            dst: The destination clock. Has to be valid and in the graph.

        Returns:
            Up to four links, at most one of each kind.
        """
        src = self.get_canonical_clock_id(src)
        dst = self.get_canonical_clock_id(dst)

        try:
            all_edges = self._graph[src][dst]
        except KeyError:
            all_edges = {}
        all_edges = [(key, attrs.get(METADATA)) for key, attrs in all_edges.items()]
        return all_edges

    def get_master(self, clock_id: ClockId) -> ClockId | None:
        """
        Retrieve the master of `clock_id`, if any.

        Args:
            clock_id: The clock ID to get the master for. Has to be a valid clock ID.

        Returns:
            The master clock ID if a master link was in the graph, otherwise `None`.
        """

        clock_id = self.get_canonical_clock_id(clock_id)
        all_in_edges = self._graph.in_edges(clock_id, keys=True)
        for src, _, key in all_in_edges:
            if key == L_MASTER:
                return src

        return None

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
        links = self.get_links(src, dst)
        diags = {}
        for key, metadata in links:
            match key, metadata:
                case "ptp_parent", PortId() as port_id:
                    diags["parent_port"] = self.diagnose_port(port_id)
                case "phc2sys", SlaveClockState() as state:
                    diags["phc2sys"] = diagnose_servo_state(state.servo_state)
                case "measurement", int() as time_diff_ns:
                    diags[f"offset_from_{readable_clock_id(dst)}"] = (
                        diagnose_clock_diff(time_diff_ns)
                    )
                case "master", int() as master_offset_ns:
                    diags["offset_from_master"] = diagnose_clock_diff(master_offset_ns)
                case _:
                    raise AssertionError(f"Unexpected link metadata: {key}: {metadata}")

        return to_diag_tree(diags)

    def diagnose_clock(self, clock: ClockId) -> DiagTree:
        """
        Diagnose whether a clock has no self-reported or upstream synchronization problems.

        Upstream is defined here as all links in the tree of ancestors of the clock. If the clock is
        part of a cycle, this is diagnosed as an error.

        The severity of all upstream links, even if there are multiple different paths, is aggregated,
        meaning that any issue in any upstream link will propagate to the clock's diagnostic status.

        Args:
            clock: The clock to diagnose

        Returns:
            The aggregated diagnostics of any self-reported clock state and upstream links.
        """

        try:
            cycle = nx.find_cycle(self._graph, clock)
            cycle_clocks: list[ClockId] = [src for src, *_ in cycle]
            return to_diag_tree(
                Error(
                    msg=f"Clock is part of the cycle {' -> '.join(map(readable_clock_id, cycle_clocks))} -> (repeats)"
                )
            )
        except nx.NetworkXNoCycle:
            pass

        ancestors = nx.ancestors(self._graph, clock)
        ancestor_graph: nx.MultiDiGraph = nx.subgraph(self._graph, ancestors | {clock})  # type: ignore
        ancestor_edges = ancestor_graph.edges()

        link_diags = [self.diagnose_link(src, dst) for src, dst in ancestor_edges]

        diag_map = {}

        if C_SELF_REPORTED_STATE in self._graph.nodes[clock]:
            diag_map["self_reported_state"] = diagnose_clock_state(
                self._graph.nodes[clock][C_SELF_REPORTED_STATE]
            )

        if link_diags:
            diag_map["upstream_links"] = link_diags
        else:
            diag_map["upstream_links"] = to_diag_tree(
                Ok(msg="Syncs to no upstream clocks")
            )

        return to_diag_tree(diag_map)

    def diagnose_reachability(self) -> DiagStatus:
        """
        Diagnose whether the graph is weakly connected.

        A graph is weakly connected when ignoring edge direction, all nodes are reachable from each other.
        This is a necessary but not sufficient condition for a well-formed sync graph.

        Returns:
            `Ok` if the graph is weakly connected, `Error` otherwise.
        """
        if self._graph.number_of_nodes() == 0:
            return DiagStatus(ok=Ok(msg="No clocks present"))
        if nx.is_weakly_connected(self._graph):
            return DiagStatus(ok=Ok(msg="There are no disconnected subgraphs"))
        return DiagStatus(
            error=Error(
                msg=f"There are {nx.number_weakly_connected_components(self._graph)} mutually unreachable subgraphs"
            )
        )

    def diagnose_cycles(self) -> DiagStatus:
        """
        Diagnose whether the graph is free of directed cycles.

        A directed graph without cycles is commonly called a directed acyclic graph, or DAG.
        Acyclicity is a necessary but not sufficient condition for a well-formed sync graph.

        Returns:
            `Ok` if the graph is a DAG, `Error` otherwise.
        """
        if nx.is_directed_acyclic_graph(self._graph):
            return DiagStatus(ok=Ok(msg="The are no cycles in the graph"))
        return DiagStatus(error=Error(msg="There are cycles in the graph"))

    def diagnose_grandmaster(self) -> DiagStatus:
        """
        Diagnoses whether there is exactly one clock acting as grandmaster.

        A grandmaster is a clock with no incoming links from which all other clocks are reachable.
        The existence of exactly one grandmaster is necessary but not sufficient for a well-formed sync graph.

        Returns:
            `Ok` if there is exactly one valid grandmaster, `Error` otherwise.
        """

        grandmaster_candiates: list[ClockId] = [
            n for n, in_degree in self._graph.in_degree() if in_degree == 0
        ]

        match grandmaster_candiates:
            case []:
                return DiagStatus(error=Error(msg="There is no grandmaster clock"))
            case [candidate]:
                grandmaster = candidate
            case _:
                return DiagStatus(
                    error=Error(msg="There is more than one grandmaster clock")
                )

        reachable_from_grandmaster: set[ClockId] = nx.descendants(
            self._graph, grandmaster
        )

        if len(reachable_from_grandmaster) == len(self._graph) - 1:
            return DiagStatus(ok=Ok(msg="All clocks sync to the same grandmaster"))

        return DiagStatus(
            error=Error(msg="Not all clocks are reachable from the grandmaster")
        )

    def diagnose_clock_reference_adherence(self) -> DiagStatus:
        """
        Compare the current graph to its reference graph (if any).

        Resulting status:

        - No reference given: `Ok`
        - All reference clocks and no other clocks present: `Ok`
        - All reference clocks and unexpected clocks present: `Warning`
        - Not all reference clocks present: `Error`

        Returns:
            The result of the comparison
        """

        if not self.reference_graph:
            return DiagStatus(ok=Ok(msg="No reference graph present"))

        expected_clocks: set[ClockId] = set(self.reference_graph.nodes)
        found_clocks: set[ClockId] = set(self._graph.nodes)

        missing_clocks = expected_clocks - found_clocks
        rogue_clocks = found_clocks - expected_clocks

        statuses = []

        if missing_clocks:
            msg = f"{len(missing_clocks)} clocks are not present: {', '.join(map(readable_clock_id, missing_clocks))}"
            statuses.append(DiagStatus(error=Error(msg=msg)))

        if rogue_clocks:
            msg = f"{len(rogue_clocks)} unexpected clocks found: {', '.join(map(readable_clock_id, rogue_clocks))}"
            statuses.append(DiagStatus(warning=Warning(msg=msg)))

        if statuses:
            return aggregate(to_diag_tree(statuses))

        return DiagStatus(
            ok=Ok(msg=f"All {len(self.reference_graph.nodes)} clocks are present")
        )

    def diagnose_link_reference_adherence(self) -> DiagStatus:
        """
        Compare the links in the current graph to its reference graph (if any).

        Since some devices do not report their direct parent directly, this check also succeeds if
        transitive parents in the reference are reported to have a master / measurement link in the
        current graph.

        For example, a reference
        ```
        A -> B
        B -> C
        ```
        and the current graph
        ```
        A -(master)-> B
        A -(measurement)-> C
        ```
        would result in a successful check.


        Resulting status:

        - No reference given: `Ok`
        - All non-grandmaster clocks have a link from their (indirect) parent: `Ok`
        - Some clocks do not have a link from any of their (indirect) parents: `Error`

        Returns:
            The result of the comparison
        """

        if not self.reference_graph:
            return DiagStatus(ok=Ok(msg="No reference graph present"))

        missing_links: list[tuple[ClockId, ClockId]] = []
        for n in self.reference_graph.nodes:
            ancestors = nx.ancestors(self.reference_graph, n)

            # Reference graph is guaranteed to be a tree, so the only node without ancestors
            # is the grandmaster (root node)
            if not ancestors:
                continue

            ancestors = map(self.get_canonical_clock_id, ancestors)

            clock_id = self.get_canonical_clock_id(n)

            # If none of the (indirect) parents in the reference have an edge to the clock in the
            # real graph, flag the edge as missing
            if not any((a, clock_id) in self._graph.edges() for a in ancestors):
                reference_parent: ClockId | None = next(
                    self.reference_graph.predecessors(n), None
                )
                if reference_parent is None:
                    raise AssertionError(
                        "A non-root node in a tree has to have one parent"
                    )
                reference_parent = self.get_canonical_clock_id(reference_parent)
                missing_links.append((n, reference_parent))

        if missing_links:
            readable_links = [
                f"{readable_clock_id(parent)} -> {readable_clock_id(clock)}"
                for clock, parent in missing_links
            ]
            msg = f"The following {len(missing_links)} links were not found: {', '.join(readable_links)}"
            return DiagStatus(error=Error(msg=msg))

        return DiagStatus(
            ok=Ok(
                msg=f"All {len(self.reference_graph.nodes)} clocks are synced in compliance with reference"
            )
        )

    def diagnose_graph(self) -> DiagTree:
        """
        Diagnose whether the structure of the sync graph is valid.

        This diagnosis checks whether:

        - the graph is [weakly connected](https://en.wikipedia.org/w/index.php?title=Connectivity_(graph_theory)#:~:text=weakly%20connected)
        - the graph is a [directed acyclic graph](https://en.wikipedia.org/wiki/Directed_acyclic_graph)
        - there is exactly one grandmaster[^1]

        These three conditions together[^2] are sufficient for the sync graph to be well-formed.

        [^1]: A grandmaster is a clock with no incoming links from which all other clocks are reachable.
        [^2]: Actually, `grandmaster` implies `reachability` but it is nice to have them both for troubleshooting.

        Returns:
            A diagnostics map consisting of:

                - `"reachability":` [diagnose_reachability][sync_graph.sync_graph.SyncGraph.diagnose_reachability]
                - `"acyclicity":` [diagnose_cycles][sync_graph.sync_graph.SyncGraph.diagnose_cycles]
                - `"grandmaster":` [diagnose_grandmaster][sync_graph.sync_graph.SyncGraph.diagnose_grandmaster]
        """
        diagnostics = {
            "reachability": self.diagnose_reachability(),
            "acyclicity": self.diagnose_cycles(),
            "grandmaster": self.diagnose_grandmaster(),
        }

        return to_diag_tree(diagnostics)

    def diagnose_reference_adherence(self) -> DiagTree:
        """
        Diagnose whether the current graph adheres to its reference graph, if any.

        Returns:
            A diagnostics map consisting of:

                - `"reference.clocks":` [diagnose_clock_reference_adherence][sync_graph.sync_graph.SyncGraph.diagnose_clock_reference_adherence]
                - `"reference.links":` [diagnose_link_reference_adherence][sync_graph.sync_graph.SyncGraph.diagnose_link_reference_adherence]
        """
        diagnostics = {
            "reference.clocks": self.diagnose_clock_reference_adherence(),
            "reference.links": self.diagnose_link_reference_adherence(),
        }

        return to_diag_tree(diagnostics)
