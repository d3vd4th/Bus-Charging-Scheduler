from __future__ import annotations
from itertools import combinations
from .models import BatteryConfig, Bus, Route


def generate_valid_plans(
    route: Route,
    battery: BatteryConfig,
    direction: str,
) -> list[list[str]]:

    station_order = route.get_station_order(direction)
    station_ids = [s.id for s in station_order]

    nodes = route.get_node_order(direction)
    origin = nodes[0]
    destination = nodes[-1]

    valid_plans: list[list[str]] = []

    for size in range(len(station_ids) + 1):
        for combo in combinations(station_ids, size):
            plan = list(combo)
            if _is_plan_valid(plan, origin, destination, route, battery.range_km):
                valid_plans.append(plan)

    return valid_plans


def _is_plan_valid(
    plan: list[str],
    origin: str,
    destination: str,
    route: Route,
    max_range_km: float,
) -> bool:
    """Check that no gap between consecutive charging points exceeds range."""
    checkpoints = [origin] + plan + [destination]
    for i in range(len(checkpoints) - 1):
        gap = route.distance_between(checkpoints[i], checkpoints[i + 1])
        if gap > max_range_km:
            return False
    return True


def score_plan(
    plan: list[str],
    bus: Bus,
    route: Route,
) -> tuple[int, float]:
    """
    Score a plan for initial selection (lower is better).

    Primary: fewer stops preferred (less total charging time).
    Secondary: more balanced spacing (lower variance in gap distances).
    """
    origin = route.endpoints[0] if bus.direction == "forward" else route.endpoints[1]
    destination = route.endpoints[1] if bus.direction == "forward" else route.endpoints[0]

    checkpoints = [origin] + plan + [destination]
    gaps = [
        route.distance_between(checkpoints[i], checkpoints[i + 1])
        for i in range(len(checkpoints) - 1)
    ]

    num_stops = len(plan)
    if gaps:
        avg = sum(gaps) / len(gaps)
        variance = sum((g - avg) ** 2 for g in gaps) / len(gaps)
    else:
        variance = 0.0

    return (num_stops, variance)
