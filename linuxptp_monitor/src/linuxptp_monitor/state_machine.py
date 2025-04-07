import re
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Callable, Generator

from journal_monitor.journal_monitor import JournalEntry

Event = Any


@dataclass
class State(ABC):
    @abstractmethod
    def parse(self, entry: JournalEntry) -> Generator[Event, None, "State"]:
        raise NotImplementedError()


@dataclass
class SystemdUnitStateChange:
    old_state: State
    new_state: State


class SystemdUnitStateMachine:
    start_stop_re = r"(?:Started|Stopped|Stopping)"

    @dataclass(eq=False)
    class Uninitialized(State):
        factory: Callable[[], State | None] = field(repr=False)

        def parse(self, entry: JournalEntry) -> Generator[Event, None, State]:
            inner_parser = self.factory()
            if inner_parser is None:
                return self
            next_state = yield from inner_parser.parse(entry)
            return next_state

        def __eq__(self, value: object) -> bool:
            return isinstance(value, SystemdUnitStateMachine.Uninitialized)

    def __init__(
        self,
        inner_state_factory: Callable[[], State | None],
        inner_state_on_exit: Callable[[State], None],
        unit_name: str,
    ):
        self._factory = inner_state_factory
        self._on_unit_stopped = inner_state_on_exit
        self._unit_prefix = unit_name.removesuffix(".service")
        self._try_initialize()

    def _try_initialize(self):
        self.state = self._factory() or SystemdUnitStateMachine.Uninitialized(
            self._factory
        )

    def _uninitialize(self):
        if hasattr(self, "state") and not isinstance(
            self.state, SystemdUnitStateMachine.Uninitialized
        ):
            self._on_unit_stopped(self.state)
        self.state = SystemdUnitStateMachine.Uninitialized(self._factory)

    def consume(
        self, entries: list[JournalEntry]
    ) -> Generator[Event | SystemdUnitStateChange, None, None]:
        old_state = deepcopy(self.state)

        for entry in entries:
            self.state = yield from self._parse(entry)

        if old_state != self.state:
            yield SystemdUnitStateChange(old_state, self.state)

    def _parse(self, entry: JournalEntry) -> Generator[Event, None, State]:
        if entry.message is None:
            return self.state

        if entry.unit.startswith("init.scope") or entry.unit.startswith("systemd"):
            if re.match(SystemdUnitStateMachine.start_stop_re, entry.message):
                self._uninitialize()
            return self.state

        if not entry.unit.startswith(self._unit_prefix):
            return self.state

        new_state = yield from self.state.parse(entry)
        return new_state
