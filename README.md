# Bus Charging Scheduler

A Streamlit web app that schedules electric bus charging stops along the Bengaluru ↔ Kochi route, handling charger contention at 4 shared stations with tunable optimisation weights.

## Quick Start

```bash
# Clone the repo
git clone <your-repo-url>
cd bus-charging-scheduler

# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

## How It Works

1. **Pick a scenario** from the dropdown (5 pre-built scenarios included)
2. **Adjust weights** using the sliders to change scheduling priorities
3. **View results** across three tabs:
   - **Scenario Input** — route, fleet, and station configuration
   - **Bus Timetables** — per-bus journey with charging stops, waits, and arrival times
   - **Station Queues** — charger usage order at each station

## How to Change a Weight

Weights control how the scheduler resolves charger conflicts. There are two ways:

### 1. Via the UI (interactive)
Drag the weight sliders at the top of the app. Changes take effect immediately.

### 2. Via the scenario file (persistent)
Edit the `weights` section in any `data/scenarios/*.json` file:

```json
{
  "weights": {
    "individual_wait": 1.0,
    "operator_fairness": 2.0,
    "overall_throughput": 1.0
  }
}
```

Higher weight → more influence on scheduling decisions.

## How to Add a New Rule

Adding a new soft rule (e.g., "priority buses charge first") requires **3 small changes**:

### Step 1: Create the rule file

```python
# scheduler/rules/priority_bus.py
from .base import ScoringRule

class PriorityBusRule(ScoringRule):
    @property
    def weight_key(self) -> str:
        return "priority_bonus"

    def score(self, bus_id, station_id, context):
        bus_priorities = context.get("bus_priorities", {})
        return 100.0 if bus_priorities.get(bus_id) == "high" else 0.0
```

### Step 2: Register it

In `scheduler/rules/__init__.py`, add:

```python
from .priority_bus import PriorityBusRule

def create_default_registry():
    registry = RuleRegistry()
    # ... existing rules ...
    registry.register(PriorityBusRule())   # ← add this
    return registry
```

### Step 3: Add the weight

In `scheduler/models.py`, add to the `Weights` dataclass:

```python
@dataclass
class Weights:
    individual_wait: float = 1.0
    operator_fairness: float = 1.0
    overall_throughput: float = 1.0
    priority_bonus: float = 0.0          # ← add this
```

That's it. No engine changes, no simulation changes.

## How to Add a New Scenario

Create a new JSON file in `data/scenarios/` following this structure:

```json
{
  "name": "My Custom Scenario",
  "description": "Description shown in the UI",
  "route": {
    "name": "Bengaluru-Kochi",
    "endpoints": ["Bengaluru", "Kochi"],
    "segments": [
      {"from": "Bengaluru", "to": "A", "distance_km": 100},
      {"from": "A", "to": "B", "distance_km": 120},
      {"from": "B", "to": "C", "distance_km": 100},
      {"from": "C", "to": "D", "distance_km": 120},
      {"from": "D", "to": "Kochi", "distance_km": 100}
    ]
  },
  "stations": [
    {"id": "A", "chargers": 1},
    {"id": "B", "chargers": 1},
    {"id": "C", "chargers": 1},
    {"id": "D", "chargers": 1}
  ],
  "battery": {"range_km": 240, "charge_time_min": 25},
  "speed_kmh": 60,
  "weights": {
    "individual_wait": 1.0,
    "operator_fairness": 1.0,
    "overall_throughput": 1.0
  },
  "fleet": [
    {"id": "bus-01", "operator": "kpn", "direction": "forward", "departure": "19:00"}
  ]
}
```

The app automatically discovers new JSON files — no code changes needed.

## Project Structure

```
├── app.py                          # Streamlit entry point
├── requirements.txt
├── data/scenarios/                 # Scenario JSON files (data, not code)
│   ├── scenario_1.json             # Even spacing
│   ├── scenario_2.json             # Bunched start
│   ├── scenario_3.json             # Asymmetric load
│   ├── scenario_4.json             # Operator-heavy
│   └── scenario_5.json             # Worst case convergence
├── scheduler/
│   ├── models.py                   # All dataclasses (input + output)
│   ├── loader.py                   # JSON → Scenario
│   ├── plan_generator.py           # Enumerates valid charging plans
│   ├── simulation.py               # Discrete event simulation engine
│   ├── optimizer.py                # Iterative plan refinement
│   ├── engine.py                   # Top-level orchestrator
│   └── rules/                      # Pluggable scoring rules
│       ├── base.py                 # ScoringRule ABC + RuleRegistry
│       ├── individual_wait.py      # Prevent individual bus starvation
│       ├── operator_fairness.py    # Balance wait across operators
│       └── throughput.py           # Minimise cascade delays
└── ui/                             # Streamlit UI components
    ├── scenario_selector.py
    ├── weight_controls.py
    ├── input_view.py
    ├── bus_timetable.py
    └── station_view.py
```

