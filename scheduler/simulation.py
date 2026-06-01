"""
Discrete Event Simulation engine for bus charging scheduling.

Processes bus arrivals at stations chronologically, resolving charger
conflicts via the pluggable rule system.  Handles both travel directions
sharing the same chargers, and supports multiple chargers per station.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from .models import (
    Bus,
    BusTimeline,
    ChargingEvent,
    Scenario,
    ScheduleResult,
    StationSchedule,
    StationSlot,
)
from .rules.base import RuleRegistry


# ════════════════════════════════════════════════════════════════
#  Internal event and state types
# ════════════════════════════════════════════════════════════════

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
    # Tracks which stations this bus has already passed through
    plan_index: int = 0   # index into the bus's charging plan


class SimulationEngine:
    """
    Event-driven simulation that schedules bus charging.

    Usage:
        engine = SimulationEngine(scenario, plans, rule_registry)
        result = engine.run()
    """

    def __init__(
        self,
        scenario: Scenario,
        plans: dict[str, list[str]],   # bus_id → station IDs in travel order
        rule_registry: RuleRegistry,
    ):
        self.scenario = scenario
        self.plans = plans
        self.registry = rule_registry

        # Event queue
        self._events: list[_Event] = []
        self._seq = 0

        # Station charger state: station_id → list of "available at" times
        # (one entry per charger)
        self._charger_available: dict[str, list[datetime]] = {}
        # Station waiting queues
        self._station_queues: dict[str, list[str]] = {}

        # Per-bus mutable state
        self._bus_state: dict[str, _BusState] = {}
        self._bus_lookup: dict[str, Bus] = {b.id: b for b in scenario.fleet}

        self._init()

    # ── Initialisation ──────────────────────────────────────────

    def _init(self) -> None:
        """Set up station state and seed initial arrival events."""
        # Stations
        for station in self.scenario.route.stations:
            self._charger_available[station.id] = [datetime.min] * station.chargers
            self._station_queues[station.id] = []

        # Buses
        for bus in self.scenario.fleet:
            self._bus_state[bus.id] = _BusState()
            plan = self.plans.get(bus.id, [])
            if not plan:
                continue  # bus makes the trip without charging (won't happen for 540km route)

            first_station = plan[0]
            origin = (
                self.scenario.route.endpoints[0]
                if bus.direction == "forward"
                else self.scenario.route.endpoints[1]
            )
            travel_min = self._travel_time_min(origin, first_station)
            arrival = bus.departure + timedelta(minutes=travel_min)
            self._push_event(arrival, "arrive", bus.id, first_station)

    # ── Event management ────────────────────────────────────────

    def _push_event(self, time: datetime, etype: str, bus_id: str, station_id: str) -> None:
        self._seq += 1
        heapq.heappush(self._events, _Event(time, self._seq, etype, bus_id, station_id))

    # ── Travel time helper ──────────────────────────────────────

    def _travel_time_min(self, from_node: str, to_node: str) -> float:
        """Minutes to travel between two nodes."""
        dist = self.scenario.route.distance_between(from_node, to_node)
        speed = self.scenario.speed_kmh
        return (dist / speed) * 60.0

    def _charge_time_min(self, station_id: str) -> float:
        """Charging duration at a station (supports per-station override)."""
        station = self.scenario.route.get_station(station_id)
        return station.charge_time_min or self.scenario.battery.charge_time_min

    # ── Core simulation loop ────────────────────────────────────

    def run(self) -> ScheduleResult:
        """Run the full simulation and return the schedule result."""
        while self._events:
            event = heapq.heappop(self._events)

            if event.event_type == "arrive":
                self._handle_arrival(event)
            elif event.event_type == "finish_charging":
                self._handle_finish_charging(event)

        return self._build_result()

    def _handle_arrival(self, event: _Event) -> None:
        """Bus arrives at a station — try to get a charger or join queue."""
        bus_id = event.bus_id
        station_id = event.station_id
        arrival_time = event.time

        # Store arrival time for wait calculation
        self._bus_state[bus_id]._arrival_at_current = arrival_time  # type: ignore[attr-defined]

        charger_idx = self._find_free_charger(station_id, arrival_time)
        if charger_idx is not None:
            self._start_charging(bus_id, station_id, arrival_time, arrival_time, charger_idx)
        else:
            self._station_queues[station_id].append(bus_id)

    def _handle_finish_charging(self, event: _Event) -> None:
        """Bus finishes charging — record event, free charger, process queue."""
        bus_id = event.bus_id
        station_id = event.station_id
        finish_time = event.time

        charge_time = self._charge_time_min(station_id)
        start_time = finish_time - timedelta(minutes=charge_time)

        # Retrieve the arrival time
        state = self._bus_state[bus_id]
        arrival_time = getattr(state, "_arrival_at_current", start_time)
        wait_min = (start_time - arrival_time).total_seconds() / 60.0

        state.total_wait_min += wait_min
        state.charging_events.append(ChargingEvent(
            station_id=station_id,
            arrival_time=arrival_time,
            charge_start_time=start_time,
            charge_end_time=finish_time,
            wait_time_min=round(wait_min, 2),
        ))
        state.plan_index += 1

        # Process queue at this station
        self._process_queue(station_id, finish_time)

        # Schedule next leg for this bus
        self._schedule_next_leg(bus_id, station_id, finish_time)

    # ── Charger management ──────────────────────────────────────

    def _find_free_charger(self, station_id: str, at_time: datetime) -> int | None:
        """Return index of a free charger, or None if all busy."""
        chargers = self._charger_available[station_id]
        for i, avail_time in enumerate(chargers):
            if avail_time <= at_time:
                return i
        return None

    def _start_charging(
        self,
        bus_id: str,
        station_id: str,
        arrival_time: datetime,
        charge_start: datetime,
        charger_idx: int,
    ) -> None:
        """Begin charging a bus on a specific charger."""
        charge_time = self._charge_time_min(station_id)
        end_time = charge_start + timedelta(minutes=charge_time)
        self._charger_available[station_id][charger_idx] = end_time
        # Store arrival for this charging stop
        self._bus_state[bus_id]._arrival_at_current = arrival_time  # type: ignore[attr-defined]
        self._push_event(end_time, "finish_charging", bus_id, station_id)

    def _process_queue(self, station_id: str, current_time: datetime) -> None:
        """If a charger just freed up and buses are waiting, pick the best one."""
        queue = self._station_queues[station_id]
        if not queue:
            return

        charger_idx = self._find_free_charger(station_id, current_time)
        if charger_idx is None:
            return

        # Pick highest priority bus
        if len(queue) == 1:
            best_bus_id = queue.pop(0)
        else:
            context = self._build_rule_context()
            best_idx = 0
            best_score = float("-inf")
            for i, bid in enumerate(queue):
                score = self.registry.compute_priority(
                    bid, station_id, context, self.scenario.weights
                )
                if score > best_score:
                    best_score = score
                    best_idx = i
            best_bus_id = queue.pop(best_idx)

        # The bus's arrival time was set when it first arrived
        arrival_time = getattr(self._bus_state[best_bus_id], "_arrival_at_current", current_time)
        self._start_charging(best_bus_id, station_id, arrival_time, current_time, charger_idx)

    # ── Next leg scheduling ─────────────────────────────────────

    def _schedule_next_leg(self, bus_id: str, from_station: str, departure_time: datetime) -> None:
        """After charging, schedule the bus's arrival at its next station (if any)."""
        plan = self.plans[bus_id]
        state = self._bus_state[bus_id]
        next_idx = state.plan_index

        if next_idx < len(plan):
            next_station = plan[next_idx]
            travel_min = self._travel_time_min(from_station, next_station)
            arrival = departure_time + timedelta(minutes=travel_min)
            self._push_event(arrival, "arrive", bus_id, next_station)
        # else: bus is heading to final destination — no more charging events

    # ── Rule context ────────────────────────────────────────────

    def _build_rule_context(self) -> dict[str, Any]:
        """Snapshot of simulation state for scoring rules."""
        bus_operators = {b.id: b.operator for b in self.scenario.fleet}

        # Operator average waits
        op_wait_totals: dict[str, list[float]] = {}
        for bus in self.scenario.fleet:
            op = bus.operator
            if op not in op_wait_totals:
                op_wait_totals[op] = []
            op_wait_totals[op].append(self._bus_state[bus.id].total_wait_min)
        operator_avg = {
            op: (sum(ws) / len(ws)) if ws else 0.0
            for op, ws in op_wait_totals.items()
        }

        # Remaining distance per bus
        remaining_dist: dict[str, float] = {}
        remaining_stops: dict[str, int] = {}
        for bus in self.scenario.fleet:
            dest = (
                self.scenario.route.endpoints[1]
                if bus.direction == "forward"
                else self.scenario.route.endpoints[0]
            )
            plan = self.plans.get(bus.id, [])
            state = self._bus_state[bus.id]

            # Current position = last completed station, or origin
            if state.charging_events:
                last_station = state.charging_events[-1].station_id
            else:
                last_station = (
                    self.scenario.route.endpoints[0]
                    if bus.direction == "forward"
                    else self.scenario.route.endpoints[1]
                )
            remaining_dist[bus.id] = self.scenario.route.distance_between(last_station, dest)
            remaining_stops[bus.id] = len(plan) - state.plan_index

        return {
            "bus_total_waits": {bid: s.total_wait_min for bid, s in self._bus_state.items()},
            "bus_operators": bus_operators,
            "operator_avg_waits": operator_avg,
            "bus_remaining_distance": remaining_dist,
            "bus_remaining_stops": remaining_stops,
        }

    # ── Result building ─────────────────────────────────────────

    def _build_result(self) -> ScheduleResult:
        """Assemble the final ScheduleResult from simulation state."""
        timelines: list[BusTimeline] = []

        for bus in self.scenario.fleet:
            state = self._bus_state[bus.id]
            events = state.charging_events

            origin = (
                self.scenario.route.endpoints[0]
                if bus.direction == "forward"
                else self.scenario.route.endpoints[1]
            )
            dest = (
                self.scenario.route.endpoints[1]
                if bus.direction == "forward"
                else self.scenario.route.endpoints[0]
            )

            # Pure driving time
            total_travel_min = self._travel_time_min(origin, dest)

            # Total charging time
            total_charge_min = sum(
                self._charge_time_min(e.station_id) for e in events
            )

            # Arrival at destination
            if events:
                last_event = events[-1]
                dist_to_dest = self.scenario.route.distance_between(
                    last_event.station_id, dest
                )
                travel_to_dest_min = (dist_to_dest / self.scenario.speed_kmh) * 60.0
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
                charging_events=events,
                total_wait_min=round(state.total_wait_min, 2),
                total_charge_min=round(total_charge_min, 2),
                total_travel_min=round(total_travel_min, 2),
                total_trip_min=round(total_trip_min, 2),
            ))

        # ── Station schedules ──
        station_schedules: list[StationSchedule] = []
        for station in self.scenario.route.stations:
            slots: list[StationSlot] = []
            for bus in self.scenario.fleet:
                for event in self._bus_state[bus.id].charging_events:
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
            station_schedules.append(StationSchedule(
                station_id=station.id,
                slots=slots,
            ))

        # ── Aggregate metrics ──
        all_waits = [t.total_wait_min for t in timelines]
        total_wait = sum(all_waits)
        max_wait = max(all_waits) if all_waits else 0.0
        avg_wait = total_wait / len(all_waits) if all_waits else 0.0

        op_totals: dict[str, list[float]] = {}
        for t in timelines:
            op_totals.setdefault(t.operator, []).append(t.total_wait_min)
        operator_avg_waits = {
            op: round(sum(ws) / len(ws), 2)
            for op, ws in op_totals.items()
        }

        return ScheduleResult(
            scenario_name=self.scenario.name,
            bus_timelines=timelines,
            station_schedules=station_schedules,
            total_wait_min=round(total_wait, 2),
            max_wait_min=round(max_wait, 2),
            avg_wait_min=round(avg_wait, 2),
            operator_avg_waits=operator_avg_waits,
        )
