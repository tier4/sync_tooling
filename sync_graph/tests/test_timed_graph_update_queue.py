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
