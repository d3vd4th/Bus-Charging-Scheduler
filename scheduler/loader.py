"""
Scenario loader — reads JSON scenario files and produces Scenario objects.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import (
    BatteryConfig,
    Bus,
    Route,
    Scenario,
    Segment,
    Station,
    Weights,
)

# Reference date for parsing time-only strings like "19:00"
_REF_DATE = datetime(2024, 1, 1)


def load_scenario(path: str | Path) -> Scenario:
    """Load a single scenario from a JSON file."""
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # ── Route ──
    segments = [
        Segment(
            from_node=s["from"],
            to_node=s["to"],
            distance_km=s["distance_km"],
            speed_kmh=s.get("speed_kmh"),
        )
        for s in data["route"]["segments"]
    ]

    stations = [
        Station(
            id=s["id"],
            chargers=s.get("chargers", 1),
            charge_time_min=s.get("charge_time_min"),
        )
        for s in data["stations"]
    ]

    route = Route(
        name=data["route"]["name"],
        endpoints=tuple(data["route"]["endpoints"]),
        segments=segments,
        stations=stations,
    )

    # ── Battery ──
    battery = BatteryConfig(
        range_km=data["battery"]["range_km"],
        charge_time_min=data["battery"]["charge_time_min"],
    )

    # ── Weights ──
    raw_weights = data.get("weights", {})
    weights = Weights(
        individual_wait=raw_weights.get("individual_wait", 1.0),
        operator_fairness=raw_weights.get("operator_fairness", 1.0),
        overall_throughput=raw_weights.get("overall_throughput", 1.0),
    )

    # ── Fleet ──
    fleet: list[Bus] = []
    for b in data["fleet"]:
        h, m = map(int, b["departure"].split(":"))
        dep_time = _REF_DATE.replace(hour=h, minute=m)
        fleet.append(
            Bus(
                id=b["id"],
                operator=b["operator"],
                direction=b["direction"],
                departure=dep_time,
            )
        )

    return Scenario(
        name=data["name"],
        description=data.get("description", ""),
        route=route,
        battery=battery,
        speed_kmh=data["speed_kmh"],
        weights=weights,
        fleet=fleet,
    )


def list_scenarios(directory: str | Path) -> list[tuple[str, Path]]:
    """
    Discover scenario files in a directory.

    Returns a list of (display_name, file_path) tuples, sorted by filename.
    """
    directory = Path(directory)
    if not directory.exists():
        return []

    scenarios: list[tuple[str, Path]] = []
    for f in sorted(directory.glob("*.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            name = data.get("name", f.stem)
        except (json.JSONDecodeError, KeyError):
            name = f.stem
        scenarios.append((name, f))

    return scenarios
