"""
Operator fairness rule — balances wait times across operators.

When one operator's fleet has accumulated more average wait time than
others, its buses receive higher priority to rebalance.
"""
from __future__ import annotations

from typing import Any

from .base import ScoringRule


class OperatorFairnessRule(ScoringRule):
    """Give priority to buses whose operator has higher average wait."""

    @property
    def weight_key(self) -> str:
        return "operator_fairness"

    def score(self, bus_id: str, station_id: str, context: dict[str, Any]) -> float:
        operator = context.get("bus_operators", {}).get(bus_id, "")
        operator_avg_waits = context.get("operator_avg_waits", {})
        return operator_avg_waits.get(operator, 0.0)
