"""Weight controls — interactive sliders for tuning optimisation weights."""
from __future__ import annotations

import streamlit as st

from scheduler.models import Weights


def render_weight_controls(defaults: Weights) -> Weights:
    """
    Render three weight sliders and return the user-selected Weights.

    Defaults come from the scenario file, but users can override them.
    """
    st.markdown("#### ⚖️ Optimisation Weights")
    st.caption("Adjust how the scheduler prioritises when resolving charger conflicts.")

    col1, col2, col3 = st.columns(3)

    with col1:
        w_individual = st.slider(
            "Individual Wait",
            min_value=0.0,
            max_value=5.0,
            value=defaults.individual_wait,
            step=0.1,
            help="Higher → no single bus should wait too long",
            key="weight_individual",
        )

    with col2:
        w_operator = st.slider(
            "Operator Fairness",
            min_value=0.0,
            max_value=5.0,
            value=defaults.operator_fairness,
            step=0.1,
            help="Higher → balance wait times across operators",
            key="weight_operator",
        )

    with col3:
        w_overall = st.slider(
            "Overall Throughput",
            min_value=0.0,
            max_value=5.0,
            value=defaults.overall_throughput,
            step=0.1,
            help="Higher → minimise total network delay",
            key="weight_overall",
        )

    return Weights(
        individual_wait=w_individual,
        operator_fairness=w_operator,
        overall_throughput=w_overall,
    )
