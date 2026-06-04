import streamlit as st
import dataclasses
from scheduler.models import Weights

def render_weight_controls(defaults: Weights) -> Weights:
    st.markdown("#### ⚖️ Optimisation Weights")
    st.caption("Adjust how the scheduler prioritises when resolving charger conflicts.")

    weight_fields = dataclasses.fields(Weights)
    
    user_selections = {}

    NUM_COLUMNS = 2
    cols = st.columns(NUM_COLUMNS)

    for index, field in enumerate(weight_fields):
        current_col = cols[index % NUM_COLUMNS]
        
        with current_col:
            display_name = field.name.replace("_", " ").title()
            default_val = getattr(defaults, field.name)
            chosen_val = st.slider(
                label=display_name,
                min_value=0.0,
                max_value=5.0,
                value=float(default_val),
                step=0.1,
                key=f"weight_{field.name}"
            )
            
            user_selections[field.name] = chosen_val

    return Weights(**user_selections)
