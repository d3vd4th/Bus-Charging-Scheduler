"""Scenario selector — dropdown to pick a scenario file."""
from __future__ import annotations

from pathlib import Path

# pyrefly: ignore [missing-import]
import streamlit as st

from scheduler.loader import list_scenarios


def render_scenario_selector(scenarios_dir: Path) -> Path | None:
    """
    Render a scenario dropdown and return the selected file path.

    Returns None if no scenarios are found.
    """
    scenarios = list_scenarios(scenarios_dir)

    if not scenarios:
        st.error("No scenario files found in `data/scenarios/`. Add JSON files to get started.")
        return None

    # Format: "Scenario 1 — Even Spacing" style labels
    labels = [f"Scenario {i+1} — {name}" for i, (name, _) in enumerate(scenarios)]

    selected_idx = st.selectbox(
        "Select Scenario",
        range(len(scenarios)),
        format_func=lambda i: labels[i],
        key="scenario_selector",
    )

    return scenarios[selected_idx][1]
