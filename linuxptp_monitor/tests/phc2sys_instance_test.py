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

from datetime import datetime, timezone
from pathlib import Path

from journal_monitor.journal_monitor import JournalEntry
from linuxptp_monitor.phc2sys_instance import Phc2SysConfig, Phc2SysRunningState
from sync_tooling_msgs.clock_id_pb2 import ClockId
from sync_tooling_msgs.linux_clock_device_id_pb2 import LinuxClockDeviceId
from sync_tooling_msgs.servo_state_pb2 import ServoState

DATA_DIR = Path(__file__).parent.absolute() / Path(__file__).stem


class _Config(Phc2SysConfig):
    """Minimal phc2sys config that skips argv/config-file parsing."""

    def __init__(self, clock_aliases: dict[str, ClockId]):
        self.clock_aliases = clock_aliases


def pytest_generate_tests(metafunc):
    fixture_to_parametrize = "journal_message_file"
    if fixture_to_parametrize not in metafunc.fixturenames:
        return

    journal_messages_dir = DATA_DIR / "journal_messages"
    assert journal_messages_dir.is_dir()

    test_cases = list(journal_messages_dir.glob("*.log"))
    metafunc.parametrize(fixture_to_parametrize, test_cases)


def test_journal_message_parsing(journal_message_file: Path):
    assert journal_message_file.is_file()

    message = journal_message_file.read_text().rstrip("\n")
    entry = JournalEntry(
        system_timestamp=datetime(2026, 10, 14, tzinfo=timezone.utc),
        monotonic_timestamp_us=4_218_683_000,
        cursor=None,
        unit="phc2sys_sys_to_enp3s0.service",
        message=message,
        priority=JournalEntry.Priority.Info,
    )
    destination = ClockId(
        linux_clock_device_id=LinuxClockDeviceId(hostname="main", clock_device_number=0)
    )
    state = Phc2SysRunningState(config=_Config(clock_aliases={"enp3s0": destination}))

    generator = state.parse(entry)
    try:
        next(generator)
    except StopIteration as stopped:
        assert stopped.value is state
    else:
        raise AssertionError("parse() yielded an event")

    parsed = state.dst_clock_states[destination]
    assert parsed.offset_ns == 7
    assert parsed.frequency_offset_ppb == -8739
    assert parsed.delay_ns == 2240
    assert parsed.servo_state == ServoState.SERVO_LOCKED
