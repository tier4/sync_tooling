# Copyright 2025 TIER IV, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import TYPE_CHECKING

import pytest
from sync_tooling_msgs.clock_alias_update_pb2 import ClockAliasUpdate
from sync_tooling_msgs.clock_master_update_pb2 import ClockMasterUpdate
from sync_tooling_msgs.phc2sys_update_pb2 import Phc2SysUpdate
from sync_tooling_msgs.port_id_pb2 import PortId
from sync_tooling_msgs.port_state_pb2 import PortState
from sync_tooling_msgs.port_state_update_pb2 import PortStateUpdate
from sync_tooling_msgs.ptp_parent_update_pb2 import PtpParentUpdate
from sync_tooling_msgs.slave_clock_state_pb2 import SlaveClockState

from .util import (
    _gu,
    graph_after_updates,
    make_master_link,
    make_measurement,
    make_phc2sys_link,
    make_ptp_link,
)

if TYPE_CHECKING:
    from sync_tooling_msgs.graph_update_pb2 import GraphUpdate


def test_clock_creation(sample_clock, config):
    # A graph containing only a single clock without a master or parent
    u = _gu(ClockMasterUpdate(clock_id=sample_clock))
    g = graph_after_updates(config, None, u)

    assert g._graph.number_of_nodes() == 1
    assert g._graph.number_of_edges() == 0


def test_clock_aliases(sample_clock_aliases, config):
    # A graph containing only a single clock without a master or parent, but two aliases
    u1 = _gu(ClockMasterUpdate(clock_id=sample_clock_aliases["system"]))
    u2 = _gu(ClockMasterUpdate(clock_id=sample_clock_aliases["ptp"]))
    u3 = _gu(
        ClockAliasUpdate(
            aliases=[sample_clock_aliases["ptp"], sample_clock_aliases["system"]]
        )
    )
    g = graph_after_updates(config, None, u1, u2, u3)

    assert g._graph.number_of_nodes() == 1
    assert g._graph.number_of_edges() == 0


def test_alias_precedence(sample_clock_aliases, config):
    updates: list[GraphUpdate] = [
        _gu(ClockMasterUpdate(clock_id=v)) for v in sample_clock_aliases.values()
    ]
    updates.append(_gu(ClockAliasUpdate(aliases=list(sample_clock_aliases.values()))))
    g = graph_after_updates(config, None, *updates)

    assert g._graph.number_of_nodes() == 1
    assert g._graph.has_node(sample_clock_aliases["sensor"])


def test_ptp_link(sample_clock, remote_clock, config):
    src = sample_clock
    dst = remote_clock

    u = _gu(PtpParentUpdate(clock_id=dst, parent=PortId(clock_id=src, port_number=1)))
    g = graph_after_updates(config, None, u)

    assert g._graph.number_of_nodes() == 2
    assert g._graph.number_of_edges() == 1
    assert g._graph.has_node(src)
    assert g._graph.has_node(dst)
    assert g._graph.has_edge(src, dst)


def test_phc2sys_link(sample_clock, nic_clock, config):
    src = sample_clock
    dst = nic_clock
    u = _gu(Phc2SysUpdate(src=src, dst=dst, clock_state=SlaveClockState()))
    g = graph_after_updates(config, None, u)

    assert g._graph.number_of_nodes() == 2
    assert g._graph.number_of_edges() == 1
    assert g._graph.has_node(src)
    assert g._graph.has_node(dst)
    assert g._graph.has_edge(src, dst)


def test_alias_after_links(sample_clock_aliases, nic_clock, remote_clock, config):
    src1 = sample_clock_aliases["system"]
    dst1 = nic_clock

    src2 = sample_clock_aliases["ptp"]
    dst2 = remote_clock

    updates = [
        _gu(Phc2SysUpdate(src=src1, dst=dst1, clock_state=SlaveClockState())),
        _gu(
            PtpParentUpdate(clock_id=dst2, parent=PortId(clock_id=src2, port_number=1))
        ),
        _gu(ClockAliasUpdate(aliases=[src1, src2])),
    ]

    g = graph_after_updates(config, None, *updates)

    assert g._graph.number_of_nodes() == 3
    assert g._graph.number_of_edges() == 2

    # Alias system clock takes precedence over alias PTP, thus making src1 the replacement for src2
    assert g._graph.has_edge(src1, dst1)
    assert g._graph.has_edge(src1, dst2)


@pytest.mark.parametrize("link_type", ["master", "measurement", "phc2sys", "ptp"])
def test_no_self_loops(nic_clock, nic_port, link_type, config):
    match link_type:
        case "master":
            us = [make_master_link(nic_clock, nic_clock, False)]
        case "measurement":
            us = [make_measurement(nic_clock, nic_clock, False)]
        case "phc2sys":
            us = [make_phc2sys_link(nic_clock, nic_clock, False)]
        case "ptp":
            us = make_ptp_link(nic_port, nic_clock, False)
        case _:
            raise AssertionError(f"Unexpected link type: {link_type}")

    g = graph_after_updates(config, None, *us)

    assert g._graph.number_of_nodes() == 1
    assert g._graph.number_of_edges() == 0


def test_clocks_referenced_in_updates_created(
    sample_clock_aliases, nic_clock, nic_port, config
):
    """Any clock referenced in a valid graph update shall be created if not existent in the graph."""
    src = nic_clock
    src_port = nic_port

    dst = sample_clock_aliases["sensor"]

    u_clock_without_master = _gu(ClockMasterUpdate(clock_id=dst))
    u_clock_with_master = _gu(ClockMasterUpdate(clock_id=dst, master=src))
    u_parent_without_port = _gu(PtpParentUpdate(clock_id=dst))
    u_parent_with_port = _gu(PtpParentUpdate(clock_id=dst, parent=src_port))
    u_alias = _gu(ClockAliasUpdate(aliases=sample_clock_aliases.values()))
    u_port_state = _gu(
        PortStateUpdate(port_id=src_port, port_state=PortState.PS_MASTER)
    )
    u_phc2sys_without_src = _gu(Phc2SysUpdate(dst=dst))
    u_phc2sys_with_src = _gu(Phc2SysUpdate(src=src, dst=dst))

    expectations = [
        (u_clock_without_master, [dst]),
        (u_clock_with_master, [src, dst]),
        (u_parent_without_port, [dst]),
        (u_parent_with_port, [src, dst]),
        (u_alias, [dst]),
        (u_port_state, [src]),
        (u_phc2sys_without_src, [dst]),
        (u_phc2sys_with_src, [src, dst]),
    ]

    for update, expected_clocks in expectations:
        g = graph_after_updates(config, None, update)
        expected_clocks = set(expected_clocks)
        actual_clocks = set(g._graph.nodes)

        assert expected_clocks == actual_clocks, f"Unexpected result for {update}"
