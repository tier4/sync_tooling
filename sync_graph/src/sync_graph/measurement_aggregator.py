import statistics
from collections import defaultdict
from typing import Iterable

from sync_tooling_msgs.clock_diff_measurement_pb2 import ClockDiffMeasurement
from sync_tooling_msgs.graph_update_pb2 import GraphUpdate


def aggregate_clock_diff_measurements(
    updates: Iterable[GraphUpdate],
) -> list[GraphUpdate]:
    """
    Aggregate ClockDiffMeasurements by grouping them by (src, dst) pairs.

    For each group, compute the median diff_ns and create a single aggregated measurement.
    All measurements in the group are removed from the iterable and replaced with the single
    aggregated one.

    Args:
        updates: An iterable of GraphUpdate messages (not limited to ClockDiffMeasurements).

    Returns:
        The `updates` iterable with all ClockDiffMeasurements grouped by (src, dst) and replaced
        with a single aggregated measurement for each group.
        Non-measurement updates are preserved as-is.
    """
    # Group measurements by (src, dst) pairs
    measurement_groups = defaultdict(list)
    non_measurement_updates = []

    for update in updates:
        if update.HasField("clock_diff_measurement"):
            measurement = update.clock_diff_measurement
            # Use a tuple of (src, dst) as the grouping key
            key = (measurement.src, measurement.dst)
            measurement_groups[key].append(measurement)
        else:
            # Keep non-measurement updates as-is
            non_measurement_updates.append(update)

    # Create aggregated measurements
    aggregated_updates = []
    for (src, dst), measurements in measurement_groups.items():
        if len(measurements) == 1:
            # If only one measurement, no aggregation needed
            aggregated_updates.append(
                GraphUpdate(clock_diff_measurement=measurements[0])
            )
        else:
            # Compute median of diff_ns values
            diff_values = [m.diff_ns for m in measurements]
            median_diff = statistics.median(diff_values)

            # Create aggregated measurement with median value
            aggregated_measurement = ClockDiffMeasurement(
                src=src, dst=dst, diff_ns=int(median_diff)
            )
            aggregated_updates.append(
                GraphUpdate(clock_diff_measurement=aggregated_measurement)
            )

    # Combine non-measurement updates with aggregated measurements
    return non_measurement_updates + aggregated_updates
