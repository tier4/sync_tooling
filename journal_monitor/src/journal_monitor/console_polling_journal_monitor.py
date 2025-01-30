from datetime import datetime
import json
import subprocess
from typing import Dict, Set

from journal_monitor.journal_monitor import JournalEntry, JournalMonitor


def json_to_journal_entry(json: dict):
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
    def __init__(self):
        super().__init__()
        self._flags: Set[str] = {"--output=json"}
        self._previous_cursor: str | None = None

    def only_current_boot(self) -> JournalMonitor:
        self._flags.add("--boot")
        return self

    def only_systemd_unit(self, unit_name: str) -> JournalMonitor:
        self._flags = {f for f in self._flags if not f.startswith("--unit=")}
        self._flags.add(f"--unit={unit_name}")
        return self

    def poll(self):
        args = ["journalctl"]
        args += self._flags
        if self._previous_cursor is not None:
            args.append(f"--after-cursor={self._previous_cursor}")
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
