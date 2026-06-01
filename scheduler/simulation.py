"""
Discrete Event Simulation engine for bus charging scheduling.

Functional implementation: Uses pure functions and local state instead of
OOP classes to manage the event loop.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable

from .models import (
    BusTimeline,
    ChargingEvent,
    Scenario,
    ScheduleResult,
    StationSchedule,
    StationSlot,
)


@dataclass(order=True)
class _Event:
    """An event in the simulation priority queue."""
    time: datetime
    seq: int = field(compare=True)           # tie-breaker for determinism
    event_type: str = field(compare=False)   # "arrive" | "finish_charging"
    bus_id: str = field(compare=False)
    station_id: str = field(compare=False)


@dataclass
class _BusState:
    """Mutable state of a bus during simulation."""
    total_wait_min: float = 0.0
    charging_events: list[ChargingEvent] = field(default_factory=list)
    plan_index: int = 0
    _arrival_at_current: datetime = datetime.min


def run_simulation(
    scenario: Scenario,
    plans: dict[str, list[str]],
    rules: dict[str, Callable[[str, str, dict[str, Any]], float]],
) -> ScheduleResult:
    """
    Run the event-driven simulation and return the schedule result.
    """
    # ── State Initialization ──
    events: list[_Event] = []
    seq = 0

    # Station state
    charger_available: dict[str, list[datetime]] = {
        s.id: [datetime.min] * s.chargers for s in scenario.route.stations
    }
    station_queues: dict[str, list[str]] = {
        s.id: [] for s in scenario.route.stations
    }

    # Bus state
    bus_states: dict[str, _BusState] = {}
    bus_lookup = {b.id: b for b in scenario.fleet}

    # Helper function for pushing events
    def push_event(time: datetime, etype: str, bus_id: str, station_id: str) -> None:
        nonlocal seq
        seq += 1
        heapq.heappush(events, _Event(time, seq, etype, bus_id, station_id))

    # Helper functions for calculations
    def travel_time_min(from_node: str, to_node: str) -> float:
        dist = scenario.route.distance_between(from_node, to_node)
        return (dist / scenario.speed_kmh) * 60.0

    def get_charge_time_min(station_id: str) -> float:
        station = scenario.route.get_station(station_id)
        return station.charge_time_min or scenario.battery.charge_time_min

    # Seed initial arrivals
    for bus in scenario.fleet:
        bus_states[bus.id] = _BusState()
        plan = plans.get(bus.id, [])
        if not plan:
            continue

        first_station = plan[0]
        origin = (
            scenario.route.endpoints[0]
            if bus.direction == "forward"
            else scenario.route.endpoints[1]
        )
        t_min = travel_time_min(origin, first_station)
        arrival = bus.departure + timedelta(minutes=t_min)
        push_event(arrival, "arrive", bus.id, first_station)

    # ── Inner logic ──
    def find_free_charger(station_id: str, at_time: datetime) -> int | None:
        for i, avail_time in enumerate(charger_available[station_id]):
            if avail_time <= at_time:
                return i
        return None

    def start_charging(
        bus_id: str, station_id: str, arrival_time: datetime,
        charge_start: datetime, charger_idx: int
    ) -> None:
        c_time = get_charge_time_min(station_id)
        end_time = charge_start + timedelta(minutes=c_time)
        charger_available[station_id][charger_idx] = end_time
        bus_states[bus_id]._arrival_at_current = arrival_time
        push_event(end_time, "finish_charging", bus_id, station_id)

    def build_rule_context() -> dict[str, Any]:
        bus_operators = {b.id: b.operator for b in scenario.fleet}

        op_wait_totals: dict[str, list[float]] = {}
        for bus in scenario.fleet:
            op = bus.operator
            op_wait_totals.setdefault(op, []).append(bus_states[bus.id].total_wait_min)
        
        operator_avg = {
            op: (sum(ws) / len(ws)) if ws else 0.0
            for op, ws in op_wait_totals.items()
        }

        remaining_dist: dict[str, float] = {}
        for bus in scenario.fleet:
            dest = (
                scenario.route.endpoints[1]
                if bus.direction == "forward"
                else scenario.route.endpoints[0]
            )
            state = bus_states[bus.id]
            last_station = state.charging_events[-1].station_id if state.charging_events else (
                scenario.route.endpoints[0] if bus.direction == "forward" else scenario.route.endpoints[1]
            )
            remaining_dist[bus.id] = scenario.route.distance_between(last_station, dest)

        return {
            "bus_total_waits": {bid: s.total_wait_min for bid, s in bus_states.items()},
            "bus_operators": bus_operators,
            "operator_avg_waits": operator_avg,
            "bus_remaining_distance": remaining_dist,
        }

    def process_queue(station_id: str, current_time: datetime) -> None:
        queue = station_queues[station_id]
        if not queue:
            return

        charger_idx = find_free_charger(station_id, current_time)
        if charger_idx is None:
            return

        if len(queue) == 1:
            best_bus_id = queue.pop(0)
        else:
            context = build_rule_context()
            best_idx = 0
            best_score = float("-inf")
            for i, bid in enumerate(queue):
                # Compute total score based on weights
                total_score = 0.0
                for weight_key, rule_func in rules.items():
                    weight_val = getattr(scenario.weights, weight_key, 0.0)
                    if weight_val > 0:
                        total_score += weight_val * rule_func(bid, station_id, context)
                
                if total_score > best_score:
                    best_score = total_score
                    best_idx = i
            best_bus_id = queue.pop(best_idx)

        arrival_time = bus_states[best_bus_id]._arrival_at_current
        start_charging(best_bus_id, station_id, arrival_time, current_time, charger_idx)

    # ── Main Event Loop ──
    while events:
        event = heapq.heappop(events)
        bus_id = event.bus_id
        station_id = event.station_id
        current_time = event.time

        if event.event_type == "arrive":
            bus_states[bus_id]._arrival_at_current = current_time
            charger_idx = find_free_charger(station_id, current_time)
            if charger_idx is not None:
                start_charging(bus_id, station_id, current_time, current_time, charger_idx)
            else:
                station_queues[station_id].append(bus_id)

        elif event.event_type == "finish_charging":
            c_time = get_charge_time_min(station_id)
            start_time = current_time - timedelta(minutes=c_time)
            
            state = bus_states[bus_id]
            arrival_time = state._arrival_at_current
            wait_min = (start_time - arrival_time).total_seconds() / 60.0

            state.total_wait_min += wait_min
            state.charging_events.append(ChargingEvent(
                station_id=station_id,
                arrival_time=arrival_time,
                charge_start_time=start_time,
                charge_end_time=current_time,
                wait_time_min=round(wait_min, 2),
            ))
            state.plan_index += 1

            process_queue(station_id, current_time)

            plan = plans[bus_id]
            if state.plan_index < len(plan):
                next_station = plan[state.plan_index]
                t_min = travel_time_min(station_id, next_station)
                arrival = current_time + timedelta(minutes=t_min)
                push_event(arrival, "arrive", bus_id, next_station)

    # ── Build Final Result ──
    timelines: list[BusTimeline] = []
    for bus in scenario.fleet:
        state = bus_states[bus.id]
        origin = (
            scenario.route.endpoints[0] if bus.direction == "forward"
            else scenario.route.endpoints[1]
        )
        dest = (
            scenario.route.endpoints[1] if bus.direction == "forward"
            else scenario.route.endpoints[0]
        )

        total_travel_min = travel_time_min(origin, dest)
        total_charge_min = sum(get_charge_time_min(e.station_id) for e in state.charging_events)

        if state.charging_events:
            last_event = state.charging_events[-1]
            dist_to_dest = scenario.route.distance_between(last_event.station_id, dest)
            travel_to_dest_min = (dist_to_dest / scenario.speed_kmh) * 60.0
            arrival_time = last_event.charge_end_time + timedelta(minutes=travel_to_dest_min)
        else:
            arrival_time = bus.departure + timedelta(minutes=total_travel_min)

        total_trip_min = (arrival_time - bus.departure).total_seconds() / 60.0

        timelines.append(BusTimeline(
            bus_id=bus.id,
            operator=bus.operator,
            direction=bus.direction,
            departure_time=bus.departure,
            arrival_time=arrival_time,
            charging_events=state.charging_events,
            total_wait_min=round(state.total_wait_min, 2),
            total_charge_min=round(total_charge_min, 2),
            total_travel_min=round(total_travel_min, 2),
            total_trip_min=round(total_trip_min, 2),
        ))

    station_schedules: list[StationSchedule] = []
    for station in scenario.route.stations:
        slots: list[StationSlot] = []
        for bus in scenario.fleet:
            for event in bus_states[bus.id].charging_events:
                if event.station_id == station.id:
                    slots.append(StationSlot(
                        bus_id=bus.id,
                        operator=bus.operator,
                        direction=bus.direction,
                        arrival_time=event.arrival_time,
                        charge_start=event.charge_start_time,
                        charge_end=event.charge_end_time,
                        wait_min=event.wait_time_min,
                    ))
        slots.sort(key=lambda s: s.charge_start)
        station_schedules.append(StationSchedule(station_id=station.id, slots=slots))

    all_waits = [t.total_wait_min for t in timelines]
    total_wait = sum(all_waits)
    max_wait = max(all_waits) if all_waits else 0.0
    avg_wait = total_wait / len(all_waits) if all_waits else 0.0

    op_totals: dict[str, list[float]] = {}
    for t in timelines:
        op_totals.setdefault(t.operator, []).append(t.total_wait_min)
    operator_avg_waits = {op: round(sum(ws) / len(ws), 2) for op, ws in op_totals.items()}

    return ScheduleResult(
        scenario_name=scenario.name,
        bus_timelines=timelines,
        station_schedules=station_schedules,
        total_wait_min=round(total_wait, 2),
        max_wait_min=round(max_wait, 2),
        avg_wait_min=round(avg_wait, 2),
        operator_avg_waits=operator_avg_waits,
    )
