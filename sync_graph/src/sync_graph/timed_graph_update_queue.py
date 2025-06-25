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
    """
    Maintains a queue of graph updates, sorted by arrival time, and limited to a maximum age.
    This class can be used to instantiate a `SyncGraph` of the system state in the last `timeout`
    seconds.
    """

    timeout: timedelta
    """
    The maximum age of graph updates kept in the queue.
    """

    _graph_updates: list[GraphUpdateStamped] = field(default_factory=list)

    @property
    def updates(self) -> list[GraphUpdate]:
        """
        Returns a list of graph updates, sorted by arrival time, and limited to `timeout` age.
        When called, also drops expired updates.
        """

        self._drop_expired_updates()

        # This optimizes the amount of renaming operations the SyncGraph has to perform.
        # Alias updates require renaming their affected clocks, ports and references to them,
        # so they should be processed at a point where there are no references to clocks yet.
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
        """
        Adds a graph update to the queue, timestamped with the current monotonic time.

        Args:
            u: The graph update to add.
        """
        self._drop_expired_updates()
        update_stamped = GraphUpdateStamped(time.monotonic(), u)
        self._graph_updates.append(update_stamped)

    def _drop_expired_updates(self):
        cutoff_timestamp = time.monotonic() - self.timeout.total_seconds()
        self._graph_updates = [
            u for u in self._graph_updates if u.receive_timestamp_s > cutoff_timestamp
        ]
