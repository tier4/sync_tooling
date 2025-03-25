from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sync_tooling_msgs.graph_update_pb2 import GraphUpdate


@dataclass
class GraphUpdateStamped:
    receive_timestamp: datetime
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
        update_stamped = GraphUpdateStamped(datetime.now(), u)
        self._graph_updates.append(update_stamped)

    def _drop_expired_updates(self):
        slice_index = 0
        cutoff_timestamp = datetime.now() - self.timeout
        for i, update_stamped in enumerate(self._graph_updates):
            if update_stamped.receive_timestamp > cutoff_timestamp:
                slice_index = i
                break

        self._graph_updates = self._graph_updates[slice_index:]
