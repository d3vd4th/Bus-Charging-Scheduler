"""
Throughput rule — minimizes cascade delays across the network.

Buses with more remaining distance to their destination receive higher
priority, because delays early in their journey compound at downstream
stations.
"""
from __future__ import annotations

from typing import Any

from .base import ScoringRule


class ThroughputRule(ScoringRule):
    """Give priority to buses with more remaining distance (reduces cascading delays)."""

    @property
    def weight_key(self) -> str:
        return "overall_throughput"

    def score(self, bus_id: str, station_id: str, context: dict[str, Any]) -> float:
        remaining = context.get("bus_remaining_distance", {})
        # Normalize by dividing by a reference distance so scores are comparable
        # Use 540 as the max route distance
        raw = remaining.get(bus_id, 0.0)
        return raw / 540.0 if raw > 0 else 0.0
