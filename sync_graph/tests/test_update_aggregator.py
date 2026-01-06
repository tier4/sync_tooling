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

#!/usr/bin/env python3
"""Simple test script for the measurement aggregator function."""

from sync_graph.update_aggregator import aggregate_clock_diff_measurements
from sync_tooling_msgs.clock_diff_measurement_pb2 import ClockDiffMeasurement
from sync_tooling_msgs.clock_master_update_pb2 import ClockMasterUpdate

from .util import _gu


def test_aggregation(sample_clock, nic_clock, remote_clock):
    a = sample_clock
    b = nic_clock
    c = remote_clock

    # Create test measurements
    measurements = [
        # Multiple measurements between a -> b
        _gu(ClockDiffMeasurement(src=a, dst=b, diff_ns=1000)),
        _gu(ClockDiffMeasurement(src=a, dst=b, diff_ns=2000)),
        _gu(ClockDiffMeasurement(src=a, dst=b, diff_ns=3000)),
        # Single measurement between b -> c
        _gu(ClockDiffMeasurement(src=b, dst=c, diff_ns=5000)),
        # Multiple measurements between c -> a
        _gu(ClockDiffMeasurement(src=c, dst=a, diff_ns=10000)),
        _gu(ClockDiffMeasurement(src=c, dst=a, diff_ns=20000)),
    ]

    # Test the aggregation
    result = aggregate_clock_diff_measurements(measurements)

    # Verify results
    measurement_updates = [u for u in result if u.HasField("clock_diff_measurement")]
    assert len(measurement_updates) == 3, (
        f"Expected 3 aggregated measurements, got {len(measurement_updates)}"
    )

    # Check that a -> b has median value of 2000 (median of [1000, 2000, 3000])
    a_to_b = next(
        u
        for u in measurement_updates
        if u.clock_diff_measurement.src == a and u.clock_diff_measurement.dst == b
    )
    assert a_to_b.clock_diff_measurement.diff_ns == 2000, (
        f"Expected 2000, got {a_to_b.clock_diff_measurement.diff_ns}"
    )

    # Check that b -> c remains unchanged (single measurement)
    b_to_c = next(
        u
        for u in measurement_updates
        if u.clock_diff_measurement.src == b and u.clock_diff_measurement.dst == c
    )
    assert b_to_c.clock_diff_measurement.diff_ns == 5000, (
        f"Expected 5000, got {b_to_c.clock_diff_measurement.diff_ns}"
    )

    # Check that c -> a has median value of 15000 (median of [10000, 20000])
    c_to_a = next(
        u
        for u in measurement_updates
        if u.clock_diff_measurement.src == c and u.clock_diff_measurement.dst == a
    )
    assert c_to_a.clock_diff_measurement.diff_ns == 15000, (
        f"Expected 15000, got {c_to_a.clock_diff_measurement.diff_ns}"
    )


def test_other_updates_untouched(sample_clock, nic_clock, remote_clock):
    a = sample_clock
    b = nic_clock
    c = remote_clock

    other_update = _gu(ClockMasterUpdate(clock_id=c, master=b, master_offset_ns=1000))

    # Create some other updates that should not be aggregated
    updates = [
        _gu(ClockDiffMeasurement(src=a, dst=c, diff_ns=5000)),
        other_update,
        _gu(ClockDiffMeasurement(src=a, dst=c, diff_ns=3000)),
    ]

    # Test the aggregation with other updates included
    result = aggregate_clock_diff_measurements(updates)

    # Verify that the other updates remain unchanged
    assert len(result) == 2, f"Expected 2 updates, got {len(result)}"
    assert other_update in result, "Other update was not preserved"
