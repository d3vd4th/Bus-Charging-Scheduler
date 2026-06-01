
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

@dataclass(frozen=True)
class Segment:
    """A stretch of road between two adjacent nodes on the route."""
    from_node: str
    to_node: str
    distance_km: float
    speed_kmh: Optional[float] = None   # per-segment override; falls back to global


@dataclass(frozen=True)
class Station:
    """A charging station along the route."""
    id: str
    chargers: int = 1
    charge_time_min: Optional[float] = None  # per-station override; falls back to battery config


@dataclass
class Route:
    """
    The full route with ordered segments and charging stations.

    Nodes are the endpoints and station locations, connected by segments.
    Example for Bengaluru–Kochi:
        nodes:    Bengaluru — A — B — C — D — Kochi
        segments: [100 km] [120 km] [100 km] [120 km] [100 km]
    """
    name: str
    endpoints: tuple[str, str]
    segments: list[Segment]
    stations: list[Station]

    # ── cached lookups built once ──

    def __post_init__(self):
        # Build cumulative distances from the forward-direction origin
        self._cum_dist: dict[str, float] = {}
        current = 0.0
        self._cum_dist[self.segments[0].from_node] = 0.0
        for seg in self.segments:
            current += seg.distance_km
            self._cum_dist[seg.to_node] = current

        # Station id → Station object
        self._station_map: dict[str, Station] = {s.id: s for s in self.stations}

    # ── public helpers ──

    @property
    def total_distance_km(self) -> float:
        return sum(s.distance_km for s in self.segments)

    @property
    def node_order_forward(self) -> list[str]:
        """All nodes in forward travel order (Bengaluru → Kochi)."""
        nodes = [self.segments[0].from_node]
        for seg in self.segments:
            nodes.append(seg.to_node)
        return nodes

    def get_node_order(self, direction: str) -> list[str]:
        """All nodes in travel order for the given direction."""
        nodes = self.node_order_forward
        if direction == "reverse":
            return list(reversed(nodes))
        return list(nodes)

    def get_station_order(self, direction: str) -> list[Station]:
        """Stations in the order a bus would encounter them."""
        node_order = self.get_node_order(direction)
        station_ids = set(self._station_map.keys())
        return [self._station_map[n] for n in node_order if n in station_ids]

    def get_station(self, station_id: str) -> Station:
        return self._station_map[station_id]

    def distance_between(self, node_a: str, node_b: str) -> float:
        """Absolute distance between any two nodes on the route."""
        return abs(self._cum_dist[node_a] - self._cum_dist[node_b])

    def cumulative_distance(self, node: str) -> float:
        """Distance from the forward-direction origin to this node."""
        return self._cum_dist[node]


@dataclass(frozen=True)
class Bus:
    """A single bus in the fleet."""
    id: str
    operator: str
    direction: str           # "forward" or "reverse"
    departure: datetime


@dataclass(frozen=True)
class BatteryConfig:
    """Battery and charging parameters."""
    range_km: float
    charge_time_min: float


@dataclass
class Weights:
    individual_wait: float = 1.0
    operator_fairness: float = 1.0
    overall_throughput: float = 1.0

    def as_dict(self) -> dict[str, float]:
        """Return all weights as a flat dict (used by the rule registry)."""
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


@dataclass
class Scenario:
    name: str
    description: str
    route: Route
    battery: BatteryConfig
    speed_kmh: float
    weights: Weights
    fleet: list[Bus]


# ════════════════════════════════════════════════════════════════
#  INTERNAL MODELS — used during scheduling
# ════════════════════════════════════════════════════════════════

@dataclass
class ChargingPlan:
    """Which stations a bus will charge at, in travel order."""
    bus_id: str
    station_ids: list[str]


# ════════════════════════════════════════════════════════════════
#  OUTPUT MODELS — the schedule the engine produces
# ════════════════════════════════════════════════════════════════

@dataclass
class ChargingEvent:
    """Record of one charging stop made by a bus."""
    station_id: str
    arrival_time: datetime
    charge_start_time: datetime
    charge_end_time: datetime
    wait_time_min: float       # minutes spent waiting for a free charger


@dataclass
class BusTimeline:
    """Complete journey timeline for a single bus."""
    bus_id: str
    operator: str
    direction: str
    departure_time: datetime
    arrival_time: datetime
    charging_events: list[ChargingEvent]
    total_wait_min: float      # sum of all waits at chargers
    total_charge_min: float    # sum of all charging durations
    total_travel_min: float    # pure driving time (distance / speed)
    total_trip_min: float      # wall-clock time departure → arrival


@dataclass
class StationSlot:
    """One completed charging slot at a station."""
    bus_id: str
    operator: str
    direction: str
    arrival_time: datetime
    charge_start: datetime
    charge_end: datetime
    wait_min: float


@dataclass
class StationSchedule:
    """Full charging schedule for one station, ordered chronologically."""
    station_id: str
    slots: list[StationSlot]


@dataclass
class ScheduleResult:
    """Complete output of the scheduling engine."""
    scenario_name: str
    bus_timelines: list[BusTimeline]
    station_schedules: list[StationSchedule]
    # Aggregate metrics
    total_wait_min: float
    max_wait_min: float
    avg_wait_min: float
    operator_avg_waits: dict[str, float]  # operator → avg wait per bus
