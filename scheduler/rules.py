
from typing import Any

def score_individual_wait(bus_id: str, station_id: str, context: dict[str, Any]) -> float:
    """Give priority to buses that have accumulated the most waiting time."""
    bus_waits = context.get("bus_total_waits", {})
    return bus_waits.get(bus_id, 0.0)


def score_operator_fairness(bus_id: str, station_id: str, context: dict[str, Any]) -> float:
    """Give priority to buses whose operator has higher average wait."""
    operator = context.get("bus_operators", {}).get(bus_id, "")
    operator_avg_waits = context.get("operator_avg_waits", {})
    return operator_avg_waits.get(operator, 0.0)


def score_throughput(bus_id: str, station_id: str, context: dict[str, Any]) -> float:
    """Give priority to buses with more remaining distance."""
    remaining = context.get("bus_remaining_distance", {})
    raw = remaining.get(bus_id, 0.0)
    return raw / 540.0 if raw > 0 else 0.0


# Registry of rules mapped to their respective weight keys
RULES = {
    "individual_wait": score_individual_wait,
    "operator_fairness": score_operator_fairness,
    "overall_throughput": score_throughput,
}
