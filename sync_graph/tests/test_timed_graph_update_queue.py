import time
from datetime import timedelta

from sync_graph.timed_graph_update_queue import TimedGraphUpdateQueue
from sync_tooling_msgs.graph_update_pb2 import GraphUpdate


def test_empty_queue():
    q = TimedGraphUpdateQueue(timedelta(seconds=2))
    assert len(q.updates) == 0


def test_queue_with_only_expired_updates():
    timeout = timedelta(microseconds=1)
    q = TimedGraphUpdateQueue(timeout)

    for _ in range(3):
        q.push(GraphUpdate())

    time.sleep(timeout.total_seconds())
    assert len(q.updates) == 0


def test_queue_with_only_unexpired_updates():
    q = TimedGraphUpdateQueue(timedelta(days=1))

    for _ in range(3):
        q.push(GraphUpdate())

    assert len(q.updates) == 3
