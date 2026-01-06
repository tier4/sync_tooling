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

"""Journal monitor implementation using journalctl subprocess."""

import json
import subprocess
from datetime import datetime
from typing import Dict, Set

from journal_monitor.journal_monitor import JournalEntry, JournalMonitor


def json_to_journal_entry(json: dict):
    """Convert a journalctl JSON object to a JournalEntry."""
    system_timestamp_us = int(json["__REALTIME_TIMESTAMP"])
    system_timestamp_us = datetime.fromtimestamp(system_timestamp_us / 1e6)
    monotonic_timestamp_us = int(json["__MONOTONIC_TIMESTAMP"])
    cursor = json["__CURSOR"]
    unit = json["_SYSTEMD_UNIT"]
    message = json.get("MESSAGE")
    priority = json.get("PRIORITY")
    if priority is not None:
        priority = JournalEntry.Priority(int(priority))

    return JournalEntry(
        system_timestamp_us, monotonic_timestamp_us, cursor, unit, message, priority
    )


class ConsolePollingJournalMonitor(JournalMonitor):
    """Journal monitor that polls journalctl via subprocess."""

    def __init__(self):
        """Initialize the journal monitor."""
        super().__init__()
        self._flags: Set[str] = {"--output=json"}
        self._startup_flags: Set[str] = set()
        self._previous_cursor: str | None = None

    def only_current_boot(self) -> JournalMonitor:
        """Filter to only entries from the current boot."""
        self._flags.add("--boot")
        return self

    def only_systemd_unit(self, unit_name: str) -> JournalMonitor:
        """Filter to only entries from the specified unit."""
        self._flags = {f for f in self._flags if not f.startswith("--unit=")}
        self._flags.add(f"--unit={unit_name}")
        return self

    def only_from_seconds_ago(self, seconds: int) -> JournalMonitor:
        """Filter to only entries from the last N seconds."""
        self._startup_flags.add(f"--since=-{seconds}s")
        return self

    def poll(self):
        """Poll journalctl for new entries since last poll."""
        args = ["journalctl"]
        args += self._flags
        if self._previous_cursor is not None:
            args.append(f"--after-cursor={self._previous_cursor}")
        else:
            args += self._startup_flags
        output = subprocess.check_output(args)
        output = output.decode()
        json_strings = output.splitlines()
        json_objs: list[Dict] = [json.loads(s) for s in json_strings]
        journal_entries: list[JournalEntry] = [
            json_to_journal_entry(j) for j in json_objs
        ]

        if journal_entries:
            self._previous_cursor = journal_entries[-1].cursor
        return journal_entries
