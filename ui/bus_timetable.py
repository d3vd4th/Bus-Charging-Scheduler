"""Bus timetable — per-bus journey timeline display."""
from __future__ import annotations

# pyrefly: ignore [missing-import]
import streamlit as st
import pandas as pd

from scheduler.models import ScheduleResult, Scenario


# Operator display colors
_OP_COLORS = {
    "kpn": "🟢",
    "freshbus": "🔵",
    "flixbus": "🟠",
}


def render_bus_timetable(result: ScheduleResult, scenario: Scenario) -> None:
    """Display the full timeline for every bus in the schedule."""

    st.markdown("##### 📊 Summary Metrics")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Wait (all buses)", f"{result.total_wait_min:.0f} min")
    col2.metric("Max Wait (single bus)", f"{result.max_wait_min:.0f} min")
    col3.metric("Avg Wait (per bus)", f"{result.avg_wait_min:.1f} min")

    # Operator breakdown
    if result.operator_avg_waits:
        st.markdown("##### 🏢 Operator Average Wait")
        op_cols = st.columns(len(result.operator_avg_waits))
        for i, (op, avg_wait) in enumerate(sorted(result.operator_avg_waits.items())):
            icon = _OP_COLORS.get(op, "⚪")
            op_cols[i].metric(f"{icon} {op.upper()}", f"{avg_wait:.1f} min")

    st.markdown("---")
    st.markdown("##### 🚌 Per-Bus Timetables")

    # Build summary table
    summary_rows = []
    for tl in result.bus_timelines:
        direction_label = (
            f"{scenario.route.endpoints[0]} → {scenario.route.endpoints[1]}"
            if tl.direction == "forward"
            else f"{scenario.route.endpoints[1]} → {scenario.route.endpoints[0]}"
        )
        stations_used = ", ".join(e.station_id for e in tl.charging_events) or "None"
        summary_rows.append({
            "Bus ID": tl.bus_id,
            "Operator": tl.operator.upper(),
            "Direction": direction_label,
            "Departure": tl.departure_time.strftime("%H:%M"),
            "Arrival": tl.arrival_time.strftime("%H:%M"),
            "Stations Used": stations_used,
            "Total Wait (min)": round(tl.total_wait_min, 1),
            "Trip Time (min)": round(tl.total_trip_min, 1),
        })

    df_summary = pd.DataFrame(summary_rows)
    st.dataframe(df_summary, use_container_width=True, hide_index=True)

    # Detailed per-bus expandable sections
    st.markdown("##### 📋 Detailed Timelines")
    st.caption("Expand any bus below to see its full journey breakdown.")

    for tl in result.bus_timelines:
        icon = _OP_COLORS.get(tl.operator, "⚪")
        wait_badge = f" — ⏱️ {tl.total_wait_min:.0f} min wait" if tl.total_wait_min > 0 else ""
        label = (
            f"{icon} **{tl.bus_id}** ({tl.operator.upper()}) | "
            f"{tl.departure_time.strftime('%H:%M')} → {tl.arrival_time.strftime('%H:%M')}"
            f"{wait_badge}"
        )

        with st.expander(label, expanded=False):
            # Journey steps
            origin = (
                scenario.route.endpoints[0]
                if tl.direction == "forward"
                else scenario.route.endpoints[1]
            )
            dest = (
                scenario.route.endpoints[1]
                if tl.direction == "forward"
                else scenario.route.endpoints[0]
            )

            steps = []

            # Departure
            steps.append({
                "Event": "🚏 Depart",
                "Location": origin,
                "Time": tl.departure_time.strftime("%H:%M"),
                "Detail": "Full charge (240 km range)",
            })

            # Charging stops
            for event in tl.charging_events:
                steps.append({
                    "Event": "📍 Arrive at station",
                    "Location": f"Station {event.station_id}",
                    "Time": event.arrival_time.strftime("%H:%M"),
                    "Detail": f"Wait: {event.wait_time_min:.0f} min" if event.wait_time_min > 0 else "No wait",
                })
                steps.append({
                    "Event": "⚡ Charging",
                    "Location": f"Station {event.station_id}",
                    "Time": f"{event.charge_start_time.strftime('%H:%M')} – {event.charge_end_time.strftime('%H:%M')}",
                    "Detail": f"{(event.charge_end_time - event.charge_start_time).total_seconds()/60:.0f} min → Full charge",
                })

            # Arrival
            steps.append({
                "Event": "🏁 Arrive",
                "Location": dest,
                "Time": tl.arrival_time.strftime("%H:%M"),
                "Detail": f"Total trip: {tl.total_trip_min:.0f} min",
            })

            df_steps = pd.DataFrame(steps)
            st.dataframe(df_steps, use_container_width=True, hide_index=True)
