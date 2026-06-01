# Architecture

## Scheduling Approach: Priority-Based Discrete Event Simulation

### What it is

The scheduler uses a **two-phase approach**:

1. **Plan Selection** — For each bus, enumerate all valid charging plans (which subset of stations A/B/C/D to charge at), then pick the best one using a spacing heuristic and iterative refinement.

2. **Conflict Resolution via Simulation** — Run a chronological event-driven simulation. When multiple buses queue at the same charger, a **weighted priority function** decides who charges first.

### Why this approach?

| Approach | Pros | Cons |
|---|---|---|
| **CP-SAT / ILP** | Globally optimal | Opaque decisions, slow at scale, heavy dependency |
| **Genetic Algorithm** | Good for large spaces | Non-deterministic, hard to reason about |
| **Priority-based DES** ✅ | Fast, explainable, extensible | Greedy (not globally optimal) |

I chose DES because:

- **Explainability**: Every scheduling decision traces to a priority score with clear weights. You can ask "why did bus X wait?" and get a concrete answer.
- **Scalability**: O(n log n) per station. Going from 20 to 200 buses adds seconds, not minutes.
- **Extensibility**: Adding a rule = adding a scoring function. No solver reformulation needed.
- **Weight sensitivity**: Weights are direct multipliers on priority terms. Change a weight → different priority order → different schedule.

The iterative optimiser on top of the greedy simulation catches most cases where a different charging plan would have avoided contention, bridging the gap toward global optimality.

---

## Data Structure Design

### The scenario file

A single JSON file is the complete source of truth for one scheduling run. It carries:

```json
{
  "name": "...",
  "description": "...",
  "route": { "segments": [...] },
  "stations": [...],
  "battery": { "range_km": 240, "charge_time_min": 25 },
  "speed_kmh": 60,
  "weights": { "individual_wait": 1.0, ... },
  "fleet": [...]
}
```

Everything the scheduler needs is in data. The code reads the scenario and operates on it generically — it never hard-codes "4 stations" or "20 buses" or "Bengaluru".

### Python data model

```
Scenario
├── Route
│   ├── endpoints: (str, str)
│   ├── segments: [Segment]        # from, to, distance_km
│   └── stations: [Station]        # id, chargers, charge_time_min
├── BatteryConfig                  # range_km, charge_time_min
├── Weights                        # individual_wait, operator_fairness, overall_throughput
└── fleet: [Bus]                   # id, operator, direction, departure
```

Output:
```
ScheduleResult
├── bus_timelines: [BusTimeline]
│   └── charging_events: [ChargingEvent]
├── station_schedules: [StationSchedule]
│   └── slots: [StationSlot]
└── metrics: total_wait, max_wait, avg_wait, operator_avg_waits
```

---

## Anticipated Future Changes

Each row describes a change the real world is likely to require, and how this design handles it.

| # | Future Change | Impact on Data | Impact on Code |
|---|---|---|---|
| 1 | **Add station E** between D and Kochi | Add segment + station to JSON | None |
| 2 | **Multiple chargers** at station B | Change `"chargers": 1` → `"chargers": 3` | None (simulation already supports N chargers) |
| 3 | **New operator** (e.g. RedBus) | Use `"operator": "redbus"` in fleet | None |
| 4 | **Different battery range** (300 km) | Change `"range_km": 300` | None |
| 5 | **50+ buses** per scenario | Add fleet entries | None |
| 6 | **Different charge time per station** | Add `"charge_time_min"` to station JSON | None (loader + simulation already read it) |
| 7 | **Different speed per segment** | Add `"speed_kmh"` to segment JSON | None (loader + simulation already read it) |
| 8 | **New route** (e.g. Chennai–Hyderabad) | New JSON file with different topology | None |
| 9 | **Priority buses** | Add `"priority": "high"` to bus JSON | New scoring rule (~20 lines) + weight field |
| 10 | **Time-of-day electricity costs** | Add cost schedule to station JSON | New scoring rule + context builder addition |
| 11 | **Driver shift constraints** (max hours) | Add `"max_drive_min"` to battery/bus | New hard-constraint validation rule |
| 12 | **Multiple routes sharing stations** | Station IDs are already strings; load multiple scenarios | Cross-route coordination rule (~30 lines) |
| 13 | **Partial charging** (not always to full) | Add charge level to ChargingEvent | Modify simulation to track SOC instead of binary full/empty |
| 14 | **Variable speed / traffic** | Add speed profile to segments or time-of-day table | Modify travel time calculation |
| 15 | **Different charger types** (fast/slow) | Add `"charger_type"` to station + different charge times | Minor simulation change to select charger type |

Changes 1–8 require **zero code changes** — they're pure data edits.
Changes 9–12 require a **single new rule file** and a weight field.
Changes 13–15 require simulation logic changes but are localised to one module.

---

## How to Change a Weight

### In the scenario file (persistent)

```json
{
  "weights": {
    "individual_wait": 1.0,
    "operator_fairness": 2.0,    ← change this value
    "overall_throughput": 1.0
  }
}
```

### In the UI (interactive)

Drag the slider. The scheduler re-runs immediately.

### Programmatically

```python
from scheduler.models import Weights
from scheduler.engine import schedule
from scheduler.loader import load_scenario

scenario = load_scenario("data/scenarios/scenario_4.json")
custom_weights = Weights(individual_wait=1.0, operator_fairness=5.0, overall_throughput=0.5)
result = schedule(scenario, weights=custom_weights)
```

---

## How to Add a New Rule

### Example: "Priority Buses Charge First"

**Step 1** — Create `scheduler/rules/priority_bus.py`:

```python
from .base import ScoringRule

class PriorityBusRule(ScoringRule):
    @property
    def weight_key(self) -> str:
        return "priority_bonus"

    def score(self, bus_id, station_id, context):
        priorities = context.get("bus_priorities", {})
        return 100.0 if priorities.get(bus_id) == "high" else 0.0
```

**Step 2** — Register in `scheduler/rules/__init__.py`:

```python
from .priority_bus import PriorityBusRule

def create_default_registry():
    registry = RuleRegistry()
    registry.register(IndividualWaitRule())
    registry.register(OperatorFairnessRule())
    registry.register(ThroughputRule())
    registry.register(PriorityBusRule())      # ← new
    return registry
```

**Step 3** — Add weight to `scheduler/models.py`:

```python
@dataclass
class Weights:
    individual_wait: float = 1.0
    operator_fairness: float = 1.0
    overall_throughput: float = 1.0
    priority_bonus: float = 0.0               # ← new
```

**Step 4** — Add `"priority": "high"` to bus entries in JSON and surface it in the simulation context builder.

Total: ~25 lines of new code. No engine changes. No simulation rewrite.

---

## Component Architecture

```
┌─────────────────────────────────────┐
│         Streamlit UI (app.py)       │
│  Scenario selector • Weight sliders │
│  Input view • Bus timetable •       │
│  Station queue view                 │
└─────────────┬───────────────────────┘
              │ calls
              ▼
┌─────────────────────────────────────┐
│     Engine (engine.py)              │
│     Orchestrates the pipeline       │
└──┬──────────┬───────────────────┬───┘
   │          │                   │
   ▼          ▼                   ▼
┌────────┐ ┌──────────────┐ ┌──────────┐
│ Plan   │ │  Simulation  │ │ Optimiser│
│ Gen    │ │  (DES)       │ │          │
└────────┘ └──────┬───────┘ └──────────┘
                  │ uses
                  ▼
           ┌──────────────┐
           │ Rule Registry │
           ├──────────────┤
           │ Individual   │
           │ Operator     │
           │ Throughput   │
           │ (+ future)   │
           └──────────────┘
```

---

## Assumptions

1. **Constant speed**: All buses travel at 60 km/h with no traffic variation
2. **Full charge only**: Charging always fills the battery to 240 km range (no partial charges)
3. **Fixed charge time**: 25 minutes at every station (overridable per station in JSON)
4. **FIFO with priority override**: When multiple buses arrive simultaneously, the priority function breaks ties; within equal priority, first-arrived goes first
5. **No overnight wrap**: All departure times are within a single calendar day
6. **Endpoints excluded**: Bengaluru and Kochi have their own slow chargers — not part of the scheduling problem
7. **No backtracking**: A bus visits stations strictly in route order
8. **Deterministic**: Same inputs always produce the same schedule
