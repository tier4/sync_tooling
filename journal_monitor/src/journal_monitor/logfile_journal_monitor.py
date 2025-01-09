from datetime import datetime
from math import floor
from os import PathLike
import re

import dateutil
import dateutil.parser

from journal_monitor.journal_monitor import JournalEntry, JournalMonitor


def line_to_journal_entry(line: str):
    journal_entry_re = r"(?P<datetime>.*) (?P<hostname>\w+) (?P<unit>\w+)\[(?P<pid>\d+)\]:\s+(?P<message>.*)$"
    m = re.match(journal_entry_re, line)

    if not m:
        return None

    system_datetime = dateutil.parser.parse(m["datetime"])
    system_timestamp_us = floor(system_datetime.timestamp() * 1e6)
    system_timestamp = datetime.fromtimestamp(system_timestamp_us * 1e-6)

    return JournalEntry(system_timestamp, None, None, m["unit"], m["message"])


class LogfileJournalMonitor(JournalMonitor):
    boot_re = r"--\s+Boot\s+\w+\s+--$"

    def __init__(self, logfile: PathLike):
        super().__init__()

        with open(logfile) as f:
            self._lines = f.readlines()

    def only_current_boot(self) -> JournalMonitor:
        i = 0
        for i, line in enumerate(reversed(self._lines)):
            if re.match(LogfileJournalMonitor.boot_re, line):
                break

        self._lines = self._lines[-i:]
        return self

    def only_systemd_unit(self, unit_name: str) -> JournalMonitor:
        def should_keep(line: str):
            entry = line_to_journal_entry(line)
            if entry is None:
                return True  # might be metadata like a boot ID
            return entry.unit in ["init.slice", "systemd", unit_name]

        self._lines = [line for line in self._lines if should_keep(line)]
        return self

    def poll(self):
        entries = [line_to_journal_entry(line) for line in self._lines]
        entries = [e for e in entries if e is not None]

        self._lines = []

        return entries
