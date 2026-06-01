"""Station view — per-station charger queue display."""
from __future__ import annotations

import streamlit as st
import pandas as pd

from scheduler.models import ScheduleResult, Scenario


_OP_COLORS = {
    "kpn": "🟢",
    "freshbus": "🔵",
    "flixbus": "🟠",
}

_DIR_ARROWS = {
    "forward": "→",
    "reverse": "←",
}


def render_station_view(result: ScheduleResult, scenario: Scenario) -> None:
    """Display the charging queue at each station."""

    st.markdown("##### ⚡ Per-Station Charging Queues")
    st.caption("Shows the order in which buses used each charger, with wait times.")

    for sched in result.station_schedules:
        dist_from_start = scenario.route.cumulative_distance(sched.station_id)
        n_slots = len(sched.slots)
        total_wait = sum(s.wait_min for s in sched.slots)

        header = (
            f"**Station {sched.station_id}** — "
            f"{int(dist_from_start)} km from {scenario.route.endpoints[0]} | "
            f"{n_slots} buses charged"
        )
        if total_wait > 0:
            header += f" | ⏱️ {total_wait:.0f} min total wait"

        with st.expander(header, expanded=True):
            if not sched.slots:
                st.info("No buses charged at this station.")
                continue

            rows = []
            for i, slot in enumerate(sched.slots, 1):
                icon = _OP_COLORS.get(slot.operator, "⚪")
                direction_label = (
                    f"{scenario.route.endpoints[0]} → {scenario.route.endpoints[1]}"
                    if slot.direction == "forward"
                    else f"{scenario.route.endpoints[1]} → {scenario.route.endpoints[0]}"
                )
                dir_arrow = _DIR_ARROWS.get(slot.direction, "?")

                rows.append({
                    "Order": i,
                    "Bus ID": slot.bus_id,
                    "Operator": f"{icon} {slot.operator.upper()}",
                    "Direction": direction_label,
                    "Arrived": slot.arrival_time.strftime("%H:%M"),
                    "Charge Start": slot.charge_start.strftime("%H:%M"),
                    "Charge End": slot.charge_end.strftime("%H:%M"),
                    "Wait (min)": round(slot.wait_min, 1),
                })

            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Visual timeline bar
            _render_timeline_bar(sched, scenario)


def _render_timeline_bar(sched, scenario) -> None:
    """Render a simple text-based timeline showing charger usage."""
    if not sched.slots:
        return

    st.caption("Charger Timeline")

    lines = []
    for slot in sched.slots:
        icon = _OP_COLORS.get(slot.operator, "⚪")
        dir_arrow = _DIR_ARROWS.get(slot.direction, "?")
        wait_str = f" (waited {slot.wait_min:.0f}m)" if slot.wait_min > 0 else ""
        line = (
            f"{icon} {slot.bus_id} {dir_arrow} │ "
            f"{slot.charge_start.strftime('%H:%M')}–{slot.charge_end.strftime('%H:%M')}"
            f"{wait_str}"
        )
        lines.append(line)

    st.code("\n".join(lines), language=None)
