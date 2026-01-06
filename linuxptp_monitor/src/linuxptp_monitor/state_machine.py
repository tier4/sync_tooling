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

"""State machine for parsing systemd unit journal entries."""

import re
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Callable, Generator

from journal_monitor.journal_monitor import JournalEntry

Event = Any


@dataclass
class State(ABC):
    """Abstract base class for state machine states."""

    @abstractmethod
    def parse(self, entry: JournalEntry) -> Generator[Event, None, "State"]:
        """Parse a journal entry and yield events, returning the next state."""
        raise NotImplementedError()


@dataclass
class SystemdUnitStateChange:
    """Event emitted when a systemd unit changes state.

    Attributes:
        old_state: The previous state.
        new_state: The new state.

    """

    old_state: State
    new_state: State


class SystemdUnitStateMachine:
    """State machine for tracking a systemd unit's state via journal entries."""

    start_stop_re = r"(?:Started|Stopped|Stopping)"

    @dataclass(eq=False)
    class Uninitialized(State):
        """State before the unit has started or after it stopped.

        Attributes:
            factory: Factory function to create the initial running state. Called when the
                unit starts. Can be called multiple times if the unit restarts.

        """

        factory: Callable[[], State | None] = field(repr=False)

        def parse(self, entry: JournalEntry) -> Generator[Event, None, State]:
            """Try to instantiate an initial state, and parse the incoming entry with it."""
            initialized_state = self.factory()
            if initialized_state is None:
                return self
            next_state = yield from initialized_state.parse(entry)
            return next_state

        def __eq__(self, value: object) -> bool:
            """Check equality with another Uninitialized state."""
            return isinstance(value, SystemdUnitStateMachine.Uninitialized)

    def __init__(
        self,
        inner_state_factory: Callable[[], State | None],
        inner_state_on_exit: Callable[[State], None],
        unit_name: str,
    ):
        """Initialize the state machine.

        Args:
            inner_state_factory: Factory to create the running state.
            inner_state_on_exit: Callback when the unit stops.
            unit_name: The systemd unit name to monitor.

        """
        self._factory = inner_state_factory
        self._on_unit_stopped = inner_state_on_exit
        self._unit_prefix = unit_name.removesuffix(".service")
        self._try_initialize()

    def _try_initialize(self):
        """Attempt to initialize from factory or set Uninitialized."""
        self.state = self._factory() or SystemdUnitStateMachine.Uninitialized(
            self._factory
        )

    def _uninitialize(self):
        """Reset to uninitialized state, calling exit callback."""
        if hasattr(self, "state") and not isinstance(
            self.state, SystemdUnitStateMachine.Uninitialized
        ):
            self._on_unit_stopped(self.state)
        self.state = SystemdUnitStateMachine.Uninitialized(self._factory)

    def consume(
        self, entries: list[JournalEntry]
    ) -> Generator[Event | SystemdUnitStateChange, None, None]:
        """Process journal entries, yielding events and state changes."""
        old_state = deepcopy(self.state)

        for entry in entries:
            self.state = yield from self._parse(entry)

        if old_state != self.state:
            yield SystemdUnitStateChange(old_state, self.state)

    def _parse(self, entry: JournalEntry) -> Generator[Event, None, State]:
        """Parse a single entry, handling start/stop events."""
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
