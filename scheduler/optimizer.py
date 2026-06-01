"""
Iterative plan optimizer — improves the initial greedy plan assignment.

Functional implementation.
"""
from __future__ import annotations
from typing import Callable, Any

from .models import Bus, Scenario, ScheduleResult, Weights
from .plan_generator import score_plan
from .simulation import run_simulation


def select_initial_plans(
    scenario: Scenario,
    plan_options: dict[str, list[list[str]]],
) -> dict[str, list[str]]:
    """Pick an initial charging plan for each bus (heuristic)."""
    bus_lookup = {b.id: b for b in scenario.fleet}
    plans: dict[str, list[str]] = {}

    for bus_id, options in plan_options.items():
        bus = bus_lookup[bus_id]
        best = min(options, key=lambda p: score_plan(p, bus, scenario.route))
        plans[bus_id] = best

    return plans


def optimize_plans(
    scenario: Scenario,
    plan_options: dict[str, list[list[str]]],
    rules: dict[str, Callable[[str, str, dict[str, Any]], float]],
    max_iterations: int = 50,
) -> tuple[dict[str, list[str]], ScheduleResult]:
    """Iteratively improve plan assignments by swapping plans for high-wait buses."""
    current_plans = select_initial_plans(scenario, plan_options)

    # Run initial simulation
    best_result = run_simulation(scenario, current_plans, rules)
    best_cost = _compute_cost(best_result, scenario.weights)

    for _ in range(max_iterations):
        worst_timeline = max(best_result.bus_timelines, key=lambda t: t.total_wait_min)

        if worst_timeline.total_wait_min <= 0:
            break

        bus_id = worst_timeline.bus_id
        improved = False

        for plan in plan_options[bus_id]:
            if plan == current_plans[bus_id]:
                continue

            trial_plans = dict(current_plans)
            trial_plans[bus_id] = plan

            result = run_simulation(scenario, trial_plans, rules)
            cost = _compute_cost(result, scenario.weights)

            if cost < best_cost:
                best_result = result
                best_cost = cost
                current_plans = trial_plans
                improved = True
                break

        if not improved:
            break

    return current_plans, best_result


def _compute_cost(result: ScheduleResult, weights: Weights) -> float:
    """Compute a scalar cost for a schedule result."""
    individual_cost = result.max_wait_min

    if result.operator_avg_waits and len(result.operator_avg_waits) > 1:
        avg_of_avgs = sum(result.operator_avg_waits.values()) / len(result.operator_avg_waits)
        operator_cost = sum(
            (v - avg_of_avgs) ** 2 for v in result.operator_avg_waits.values()
        ) / len(result.operator_avg_waits)
    else:
        operator_cost = 0.0

    throughput_cost = result.total_wait_min

    return (
        weights.individual_wait * individual_cost
        + weights.operator_fairness * operator_cost
        + weights.overall_throughput * throughput_cost
    )
