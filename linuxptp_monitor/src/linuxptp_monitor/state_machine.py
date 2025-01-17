from abc import ABC
from copy import deepcopy
from dataclasses import dataclass, field
import re
from typing import Callable

from journal_monitor.journal_monitor import JournalEntry


@dataclass
class State(ABC):
    def parse(self, entry: JournalEntry) -> "State":
        raise NotImplementedError()


@dataclass
class SystemdUnitStateChange:
    old_state: State
    new_state: State


class SystemdUnitStateMachine:
    start_stop_re = r"(?:Started|Stopped|Stopping)"

    @dataclass(eq=False)
    class Uninitialized(State):
        factory: Callable[[], State] = field(repr=False)

        def parse(self, entry: JournalEntry):
            inner_parser = self.factory()
            return inner_parser.parse(entry)

        def __eq__(self, value: object) -> bool:
            return isinstance(value, SystemdUnitStateMachine.Uninitialized)

    def __init__(
        self,
        inner_state_factory: Callable[[], State],
        inner_state_on_exit: Callable[[State], None],
        unit_name: str,
    ):
        self._factory = inner_state_factory
        self._on_unit_stopped = inner_state_on_exit
        self._unit_prefix = unit_name.removesuffix(".service")
        self._uninitialize()

    def _uninitialize(self):
        if hasattr(self, "state") and not isinstance(
            self.state, SystemdUnitStateMachine.Uninitialized
        ):
            self._on_unit_stopped(self.state)
        self.state = SystemdUnitStateMachine.Uninitialized(self._factory)

    def consume(self, entry: JournalEntry) -> SystemdUnitStateChange | None:
        old_state = deepcopy(self.state)
        self.state = self._parse(entry)

        if old_state != self.state:
            return SystemdUnitStateChange(old_state, self.state)

    def _parse(self, entry: JournalEntry) -> State:
        if entry.message is None:
            return self.state

        if entry.unit.startswith("init.scope") or entry.unit.startswith("systemd"):
            if re.match(SystemdUnitStateMachine.start_stop_re, entry.message):
                self._uninitialize()
            return self.state

        if not entry.unit.startswith(self._unit_prefix):
            return self.state

        return self.state.parse(entry)
