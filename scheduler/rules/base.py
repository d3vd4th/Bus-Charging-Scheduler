"""
Base classes for the pluggable rule system.

To add a new scheduling rule:
  1. Create a new file in scheduler/rules/
  2. Subclass ScoringRule, implement weight_key and score()
  3. Register it in scheduler/rules/__init__.py
  4. Add the matching weight field to Weights in models.py

That's it — no engine changes required.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..models import Weights


class ScoringRule(ABC):
    """
    A pluggable soft rule that influences charger queue priority.

    Each rule computes a score for a bus waiting at a station.
    Higher score → higher priority → charges sooner.
    The score is multiplied by the corresponding weight from Weights.
    """

    @property
    @abstractmethod
    def weight_key(self) -> str:
        """
        The field name in Weights that controls this rule.
        Must match exactly.
        """
        ...

    @abstractmethod
    def score(self, bus_id: str, station_id: str, context: dict[str, Any]) -> float:
        """
        Compute a priority score for *bus_id* at *station_id*.

        Args:
            bus_id:     The bus requesting a charger.
            station_id: The station where the bus is queued.
            context:    Snapshot of current simulation state, containing:
                - bus_total_waits:        dict[bus_id, float]  (minutes waited so far)
                - bus_operators:          dict[bus_id, str]    (operator name)
                - operator_avg_waits:     dict[operator, float] (avg wait per operator)
                - bus_remaining_distance: dict[bus_id, float]  (km left to destination)
                - bus_remaining_stops:    dict[bus_id, int]    (charging stops remaining)

        Returns:
            A float score.  Higher = higher priority.
        """
        ...


class RuleRegistry:
    """
    Registry of scoring rules.

    Computes a weighted sum of all registered rules to determine
    charger queue priority.
    """

    def __init__(self) -> None:
        self._rules: list[ScoringRule] = []

    def register(self, rule: ScoringRule) -> None:
        """Add a rule to the registry."""
        self._rules.append(rule)

    @property
    def rules(self) -> list[ScoringRule]:
        return list(self._rules)

    def compute_priority(
        self,
        bus_id: str,
        station_id: str,
        context: dict[str, Any],
        weights: Weights,
    ) -> float:
        """
        Compute the total weighted priority score for a bus at a station.

        Returns a float — higher means this bus should charge sooner.
        """
        total = 0.0
        weight_dict = weights.as_dict()
        for rule in self._rules:
            w = weight_dict.get(rule.weight_key, 0.0)
            if w > 0:
                total += w * rule.score(bus_id, station_id, context)
        return total
