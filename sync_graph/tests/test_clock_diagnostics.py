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

import pytest
from sync_tooling_msgs.clock_master_update_pb2 import ClockMasterUpdate
from sync_tooling_msgs.port_state_pb2 import PortState
from sync_tooling_msgs.port_state_update_pb2 import PortStateUpdate
from sync_tooling_msgs.self_reported_clock_state_update_pb2 import (
    SelfReportedClockStateUpdate as ClockStateUpdate,
)

from .util import (
    _gu,
    aggregated_status_label,
    graph_after_updates,
    make_measurement,
    make_phc2sys_link,
)


@pytest.mark.parametrize("clock_setup", ["plain", "ok_port", "faulty_port"])
@pytest.mark.parametrize(
    "self_reported_state,expected_status",
    [
        (None, "ok"),
        (ClockStateUpdate.State.LOCKED, "ok"),
        (ClockStateUpdate.State.TRACKING, "warning"),
        (ClockStateUpdate.State.UNSYNCHRONIZED, "error"),
    ],
)
def test_single_clock(
    nic_port, clock_setup, self_reported_state, expected_status, config
):
    """A single clock by itself shall always be `Ok`, even if it has faulty ports."""
    clock_id = nic_port.clock_id

    us = []

    match clock_setup:
        case "plain":
            us.append(_gu(ClockMasterUpdate(clock_id=clock_id)))
        case "ok_port":
            us.append(
                _gu(PortStateUpdate(port_id=nic_port, port_state=PortState.PS_MASTER))
            )
        case "faulty_port":
            us.append(
                _gu(PortStateUpdate(port_id=nic_port, port_state=PortState.PS_FAULTY))
            )
        case _:
            raise AssertionError()

    if self_reported_state is not None:
        us.append(_gu(ClockStateUpdate(clock_id=clock_id, state=self_reported_state)))

    g = graph_after_updates(config, None, *us)

    assert clock_id in g._graph.nodes
    diag_tree = g.diagnose_clock(clock_id)
    assert aggregated_status_label(diag_tree) == expected_status


def test_cycle(sample_clock, remote_clock, nic_clock, config):
    """All clocks in a cycle shall be diagnosed as `Error`, clocks not in the cycle shall be unaffected."""
    cycle_clock_1 = sample_clock
    cycle_clock_2 = nic_clock
    unaffected_clock = remote_clock

    us = [
        make_phc2sys_link(cycle_clock_1, cycle_clock_2, False),
        make_phc2sys_link(cycle_clock_2, cycle_clock_1, False),
        make_measurement(cycle_clock_1, unaffected_clock, False),
    ]

    g = graph_after_updates(config, None, *us)

    for cycle_clock in (cycle_clock_1, cycle_clock_2):
        assert aggregated_status_label(g.diagnose_clock(cycle_clock)) == "error"

    assert aggregated_status_label(g.diagnose_clock(unaffected_clock)) == "ok"
