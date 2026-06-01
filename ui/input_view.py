"""Input view — displays the raw scenario data so reviewers can see what's being fed in."""
from __future__ import annotations

# pyrefly: ignore [missing-import]
import streamlit as st
import pandas as pd

from scheduler.models import Scenario


# Operator → colour for visual distinction
OPERATOR_COLORS = {
    "kpn": "#4CAF50",       # green
    "freshbus": "#2196F3",  # blue
    "flixbus": "#FF9800",   # orange
}


def render_input_view(scenario: Scenario) -> None:
    """Display the scenario input data: route info + fleet table."""

    # ── Route summary ──
    st.markdown("##### 🛣️ Route")
    segments_data = []
    cum_dist = 0.0
    for seg in scenario.route.segments:
        cum_dist += seg.distance_km
        segments_data.append({
            "From": seg.from_node,
            "To": seg.to_node,
            "Distance (km)": int(seg.distance_km),
            "Cumulative (km)": int(cum_dist),
        })

    df_route = pd.DataFrame(segments_data)
    st.dataframe(df_route, use_container_width=True, hide_index=True)

    # ── Config summary ──
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Battery Range", f"{int(scenario.battery.range_km)} km")
    col2.metric("Charge Time", f"{int(scenario.battery.charge_time_min)} min")
    col3.metric("Travel Speed", f"{int(scenario.speed_kmh)} km/h")
    col4.metric("Fleet Size", f"{len(scenario.fleet)} buses")

    # ── Fleet table ──
    st.markdown("##### 🚌 Fleet")

    fleet_data = []
    for bus in scenario.fleet:
        direction_label = (
            f"{scenario.route.endpoints[0]} → {scenario.route.endpoints[1]}"
            if bus.direction == "forward"
            else f"{scenario.route.endpoints[1]} → {scenario.route.endpoints[0]}"
        )
        fleet_data.append({
            "Bus ID": bus.id,
            "Operator": bus.operator.upper(),
            "Direction": direction_label,
            "Departure": bus.departure.strftime("%H:%M"),
        })

    df_fleet = pd.DataFrame(fleet_data)
    st.dataframe(df_fleet, use_container_width=True, hide_index=True)

    # ── Station info ──
    st.markdown("##### ⚡ Charging Stations")
    station_data = []
    for station in scenario.route.stations:
        charge_time = station.charge_time_min or scenario.battery.charge_time_min
        dist_from_start = scenario.route.cumulative_distance(station.id)
        station_data.append({
            "Station": station.id,
            "Chargers": station.chargers,
            "Charge Time (min)": int(charge_time),
            "Distance from Bengaluru (km)": int(dist_from_start),
        })

    df_stations = pd.DataFrame(station_data)
    st.dataframe(df_stations, use_container_width=True, hide_index=True)
