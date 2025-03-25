import logging
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
    threshold_us = 500
    if abs(time_diff_ns) <= threshold_us * 1e3:
        return to_diag_tree(Ok(msg=f"Within bounds of {threshold_us} µs"))
    return to_diag_tree(Error(msg=f"Exceeds bounds of {threshold_us} µs"))


C_STATUS_MSG = "status_msg"
C_PORT_IDS = "port_ids"

L_METADATA = "metadata"
L_TIME_DIFF = "time_diff"
L_STATUS_MSG = "status_msg"

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
        self._graph.add_edge(master_id, clock_id, L_MASTER)

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

        if u.parent.port_number == 0:
            return

        parent_port = self.get_or_create_port(u.parent)
        src_clock = self.get_or_create_clock(parent_port.clock_id)

        updated_port_ids = {
            self.get_canonical_port_id(p)
            for p in _get_node_attr(self._graph, src_clock, C_PORT_IDS) or set()  # type: ignore
        }  # type: ignore

        updated_port_ids.add(parent_port)
        _set_node_attr(self._graph, src_clock, C_PORT_IDS, updated_port_ids)

        self._graph.add_edge(
            src_clock, dst_clock, L_PTP_PARENT, **{L_METADATA: parent_port}
        )

    def update_ptp_port_state(self, u: PortStateUpdate):
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

        src = self.get_or_create_clock(u.src)
        self._graph.add_edge(src, dst, L_PHC2SYS, **{L_METADATA: u.clock_state})

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

        self._graph.add_edge(src, dst, L_MEASUREMENT, **{L_METADATA: m.diff_ns})

    def get_links(
        self, src: ClockId, dst: ClockId
    ) -> dict[str, None | SlaveClockState | PortId | int]:
        src = self.get_canonical_clock_id(src)
        dst = self.get_canonical_clock_id(dst)

        try:
            all_edges = self._graph[src][dst]
        except KeyError:
            all_edges = {}
        all_edges = {key: attrs.get(L_METADATA) for key, attrs in all_edges.items()}
        return all_edges

    def get_master(self, clock_id: ClockId) -> ClockId | None:
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
        diags = []
        for key, metadata in links.items():
            match key, metadata:
                case "ptp_parent", PortId() as port_id:
                    diags.append(self.diagnose_port(port_id))
                case "phc2sys", SlaveClockState() as state:
                    diags.append(diagnose_servo_state(state.servo_state))
                case "measurement", int() as time_diff_ns:
                    diags.append(diagnose_clock_diff(time_diff_ns))
                case "master", None:
                    diags.append(to_diag_tree(Ok(msg="Master present")))
                case _:
                    logging.error(f"{key}, {metadata}")

        return to_diag_tree(diags)

    def diagnose_clock(self, clock_id: ClockId) -> DiagTree:
        ports = self.get_ports(clock_id)

        return DiagTree(
            list=DiagTree.DiagList(list=[self.diagnose_port(p) for p in ports])
        )

    def _diagnose_reachability(self) -> DiagStatus:
        if nx.is_weakly_connected(self._graph):
            return DiagStatus(ok=Ok())
        return DiagStatus(
            error=Error(
                msg=f"There are {nx.number_weakly_connected_components(self._graph)} mutually unreachable subgraphs"
            )
        )

    def _diagnose_cycles(self) -> DiagStatus:
        if nx.is_directed_acyclic_graph(self._graph):
            return DiagStatus(ok=Ok())
        return DiagStatus(error=Error(msg="There are loops in the graph"))

    def _diagnose_grandmaster(self) -> DiagStatus:
        grandmaster_candiates: list[ClockId] = [
            n for n, in_degree in self._graph.in_degree() if in_degree == 0
        ]

        match grandmaster_candiates:
            case []:
                return DiagStatus(
                    error=Error(msg="There are no clocks without a parent/master")
                )
            case [candidate]:
                grandmaster = candidate
            case _:
                return DiagStatus(
                    error=Error(
                        msg="There is more than one clock without a parent/master"
                    )
                )

        reachable_from_grandmaster: set[ClockId] = nx.descendants(
            self._graph, grandmaster
        )

        if len(reachable_from_grandmaster) == len(self._graph) - 1:
            return DiagStatus(
                ok=Ok(msg="There is exactly one grandmaster which all clocks sync to")
            )

        return DiagStatus(
            error=Error(msg="Not all clocks are reachable from the grandmaster")
        )

    def _diagnose_if_clocks_match_reference(self) -> DiagStatus:
        """
        Compare the current graph to its reference graph (if any).

        Resulting status:
        - No reference given: Ok
        - All reference clocks and no other clocks present: Ok
        - All reference clocks and unexpected clocks present: Warning
        - Not all reference clocks present: Error

        Returns:
            DiagStatus: The result of the comparison
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

    def _diagnose_if_links_match_reference(self) -> DiagStatus:
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
        - No reference given: Ok
        - All non-grandmaster clocks have a link from their (indirect) parent: Ok
        - Some clocks do not have a link from any of their (indirect) parents: Error

        Returns:
            DiagStatus: The result of the comparison
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
            if not any((a, clock_id) in self._graph.edges for a in ancestors):
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
            msg = f"The following links were not found: {', '.join(readable_links)}"
            return DiagStatus(error=Error(msg=msg))

        return DiagStatus(
            ok=Ok(
                msg=f"All {len(self.reference_graph.nodes)} have links compliant with reference"
            )
        )

    def diagnose_graph(self) -> DiagTree:
        diagnostics = {
            "reachability": self._diagnose_reachability(),
            "acyclicity": self._diagnose_cycles(),
            "grandmaster": self._diagnose_grandmaster(),
        }

        if self.reference_graph:
            diagnostics["reference.clocks"] = self._diagnose_if_clocks_match_reference()
            diagnostics["reference.links"] = self._diagnose_if_links_match_reference()

        return to_diag_tree(diagnostics)
