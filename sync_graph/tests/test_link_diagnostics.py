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

from .util import (
    aggregated_status_label,
    graph_after_updates,
    make_master_link,
    make_measurement,
    make_phc2sys_link,
    make_ptp_link,
)


@pytest.mark.parametrize("is_faulty,expected_status", [(True, "error"), (False, "ok")])
@pytest.mark.parametrize("link_type", ["phc2sys", "ptp", "master", "measurement"])
def test_link_diagnostics(
    nic_port, sample_clock, is_faulty, expected_status, link_type, config
):
    """Test diagnostics for known-ok and known-faulty links.

    The status of the source clock shall be unaffected by any faults, while the status of the destination clock
    shall inherit the aggregated status of the link itself and the source clock's status.

    Here, the source ok is always okay, so the destination clock status shall be equal to the link status.
    """
    src_port = nic_port
    src = src_port.clock_id
    dst = sample_clock

    match link_type:
        case "master":
            us = [make_master_link(src, dst, is_faulty)]
        case "measurement":
            us = [make_measurement(src, dst, is_faulty)]
        case "phc2sys":
            us = [make_phc2sys_link(src, dst, is_faulty)]
        case "ptp":
            us = make_ptp_link(src_port, dst, is_faulty)
        case _:
            raise AssertionError()

    g = graph_after_updates(config, None, *us)
    link_diag = g.diagnose_link(src, dst)
    assert aggregated_status_label(link_diag) == expected_status
    dst_diag = g.diagnose_clock(dst)
    assert aggregated_status_label(dst_diag) == expected_status
    src_diag = g.diagnose_clock(src)
    assert aggregated_status_label(src_diag) == "ok"
