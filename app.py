from __future__ import annotations
from pathlib import Path
import streamlit as st
from scheduler.engine import schedule
from scheduler.loader import load_scenario
from scheduler.models import Weights
from ui.scenario_selector import render_scenario_selector
from ui.weight_controls import render_weight_controls
from ui.input_view import render_input_view
from ui.bus_timetable import render_bus_timetable
from ui.station_view import render_station_view

# ════════════════════════════════════════════════════════════════
#  Page config
# ════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Bus Charging Scheduler",
    page_icon="🚌",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ════════════════════════════════════════════════════════════════
#  Custom CSS — premium dark-accented theme
# ════════════════════════════════════════════════════════════════

st.markdown("""
<style>
    /* ── Typography ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* ── Header styling ── */
    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 2rem 2.5rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        border: 1px solid rgba(255, 255, 255, 0.06);
    }
    .main-header h1 {
        color: #e0e0e0;
        font-weight: 700;
        font-size: 2rem;
        margin: 0 0 0.3rem 0;
        letter-spacing: -0.02em;
    }
    .main-header p {
        color: #94a3b8;
        font-size: 1rem;
        margin: 0;
        font-weight: 400;
    }

    /* ── Metric cards ── */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #1e293b, #0f172a);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1rem 1.25rem;
    }
    [data-testid="stMetricLabel"] {
        color: #94a3b8 !important;
        font-size: 0.8rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    [data-testid="stMetricValue"] {
        color: #e2e8f0 !important;
        font-weight: 600;
    }

    /* ── Expander styling ── */
    .streamlit-expanderHeader {
        font-weight: 500;
        font-size: 0.95rem;
    }

    /* ── Dataframe styling ── */
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
    }

    /* ── Tab styling ── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 24px;
        font-weight: 500;
    }

    /* ── Divider ── */
    hr {
        border: none;
        border-top: 1px solid rgba(255, 255, 255, 0.06);
        margin: 1.5rem 0;
    }

    /* ── Scenario description badge ── */
    .scenario-desc {
        background: rgba(99, 102, 241, 0.12);
        border: 1px solid rgba(99, 102, 241, 0.25);
        border-radius: 8px;
        padding: 0.75rem 1rem;
        color: #a5b4fc;
        font-size: 0.9rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════
#  Header
# ════════════════════════════════════════════════════════════════

st.markdown("""
<div class="main-header">
    <h1>🚌 Bus Charging Scheduler</h1>
    <p>Electric bus charging optimisation for the Bengaluru ↔ Kochi corridor</p>
</div>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════
#  Scenario selection
# ════════════════════════════════════════════════════════════════

SCENARIOS_DIR = Path(__file__).parent / "data" / "scenarios"

selected_path = render_scenario_selector(SCENARIOS_DIR)

if selected_path is None:
    st.stop()

scenario = load_scenario(selected_path)

# Show scenario description
st.markdown(f'<div class="scenario-desc">📝 {scenario.description}</div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════
#  Weight controls
# ════════════════════════════════════════════════════════════════

weights = render_weight_controls(scenario.weights)

st.markdown("---")

# ════════════════════════════════════════════════════════════════
#  Run scheduler
# ════════════════════════════════════════════════════════════════

with st.spinner("Running scheduler..."):
    result = schedule(scenario, weights=weights)

# ════════════════════════════════════════════════════════════════
#  Results in tabs
# ════════════════════════════════════════════════════════════════

tab_input, tab_buses, tab_stations = st.tabs([
    "📄 Scenario Input",
    "🚌 Bus Timetables",
    "⚡ Station Queues",
])

with tab_input:
    render_input_view(scenario)

with tab_buses:
    render_bus_timetable(result, scenario)

with tab_stations:
    render_station_view(result, scenario)
