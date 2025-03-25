import time
from dataclasses import dataclass, field
from datetime import timedelta

from sync_tooling_msgs.graph_update_pb2 import GraphUpdate


@dataclass
class GraphUpdateStamped:
    receive_timestamp_s: float
    u: GraphUpdate


@dataclass
class TimedGraphUpdateQueue:
    timeout: timedelta

    _graph_updates: list[GraphUpdateStamped] = field(default_factory=list)

    @property
    def updates(self):
        self._drop_expired_updates()
        return (update_stamped.u for update_stamped in self._graph_updates)

    def push(self, u: GraphUpdate):
        update_stamped = GraphUpdateStamped(time.monotonic(), u)
        self._graph_updates.append(update_stamped)

    def _drop_expired_updates(self):
        cutoff_timestamp = time.monotonic() - self.timeout.total_seconds()
        self._graph_updates = [
            u for u in self._graph_updates if u.receive_timestamp_s > cutoff_timestamp
        ]
