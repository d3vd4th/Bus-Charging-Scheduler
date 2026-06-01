"""
Scheduling engine — top-level orchestrator.

This is the single entry point for running the scheduler:
    from scheduler.engine import schedule
    result = schedule(scenario)

Pipeline:
    1. Generate valid charging plans per direction
    2. Select + optimise plan assignments
    3. Simulate with conflict resolution
    4. Return ScheduleResult
"""
from __future__ import annotations

from typing import Optional

from .models import Scenario, ScheduleResult, Weights
from .optimizer import optimize_plans
from .plan_generator import generate_valid_plans
from .rules import create_default_registry
from .rules.base import RuleRegistry


def schedule(
    scenario: Scenario,
    weights: Optional[Weights] = None,
    registry: Optional[RuleRegistry] = None,
) -> ScheduleResult:
    """
    Run the full scheduling pipeline for a scenario.

    Args:
        scenario:  The loaded scenario to schedule.
        weights:   Optional weight overrides (e.g. from UI sliders).
                   If None, uses the scenario's built-in weights.
        registry:  Optional custom rule registry.
                   If None, uses the default set of built-in rules.

    Returns:
        A ScheduleResult with per-bus timelines and per-station schedules.
    """
    # Apply weight overrides if provided
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

    if registry is None:
        registry = create_default_registry()

    # ── Phase 1: Generate valid plans per direction ──
    forward_plans = generate_valid_plans(
        scenario.route, scenario.battery, "forward"
    )
    reverse_plans = generate_valid_plans(
        scenario.route, scenario.battery, "reverse"
    )

    # Map each bus to its valid plan options
    plan_options: dict[str, list[list[str]]] = {}
    for bus in scenario.fleet:
        if bus.direction == "forward":
            plan_options[bus.id] = forward_plans
        else:
            plan_options[bus.id] = reverse_plans

    # ── Phase 2: Optimise plan assignments + simulate ──
    _, result = optimize_plans(scenario, plan_options, registry)

    return result
