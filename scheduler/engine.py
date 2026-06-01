"""
Scheduling engine — top-level orchestrator.

Functional implementation.
"""
from __future__ import annotations
from typing import Optional, Callable, Any

from .models import Scenario, ScheduleResult, Weights
from .optimizer import optimize_plans
from .plan_generator import generate_valid_plans
from .rules import RULES


def schedule(
    scenario: Scenario,
    weights: Optional[Weights] = None,
    rules: Optional[dict[str, Callable[[str, str, dict[str, Any]], float]]] = None,
) -> ScheduleResult:
    """
    Run the full scheduling pipeline for a scenario.
    """
    if weights is not None:
        scenario = Scenario(
            name=scenario.name,
            description=scenario.description,
            route=scenario.route,
            battery=scenario.battery,
            speed_kmh=scenario.speed_kmh,
            weights=weights,
            fleet=scenario.fleet,
        )

    if rules is None:
        rules = RULES

    # ── Phase 1: Generate valid plans per direction ──
    forward_plans = generate_valid_plans(scenario.route, scenario.battery, "forward")
    reverse_plans = generate_valid_plans(scenario.route, scenario.battery, "reverse")

    plan_options: dict[str, list[list[str]]] = {}
    for bus in scenario.fleet:
        if bus.direction == "forward":
            plan_options[bus.id] = forward_plans
        else:
            plan_options[bus.id] = reverse_plans

    # ── Phase 2: Optimise plan assignments + simulate ──
    _, result = optimize_plans(scenario, plan_options, rules)

    return result
