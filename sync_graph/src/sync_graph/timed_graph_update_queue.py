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

        def get_type_precedence(u: GraphUpdate):
            match u.WhichOneof("update"):
                case "clock_alias_update":
                    return 0
                case "ptp_parent_update":
                    return 1
                case _:
                    return 1000

        return sorted(
            (update_stamped.u for update_stamped in self._graph_updates),
            key=get_type_precedence,
        )

    def push(self, u: GraphUpdate):
        self._drop_expired_updates()
        update_stamped = GraphUpdateStamped(time.monotonic(), u)
        self._graph_updates.append(update_stamped)

    def _drop_expired_updates(self):
        cutoff_timestamp = time.monotonic() - self.timeout.total_seconds()
        self._graph_updates = [
            u for u in self._graph_updates if u.receive_timestamp_s > cutoff_timestamp
        ]
