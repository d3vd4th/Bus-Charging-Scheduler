"""
Individual wait rule — prevents bus starvation.

Buses that have already waited longer at previous stations receive
higher priority, ensuring no single bus accumulates extreme delays.
"""
from __future__ import annotations

from typing import Any

from .base import ScoringRule


class IndividualWaitRule(ScoringRule):
    """Give priority to buses that have accumulated the most waiting time."""

    @property
    def weight_key(self) -> str:
        return "individual_wait"

    def score(self, bus_id: str, station_id: str, context: dict[str, Any]) -> float:
        bus_waits = context.get("bus_total_waits", {})
        return bus_waits.get(bus_id, 0.0)
