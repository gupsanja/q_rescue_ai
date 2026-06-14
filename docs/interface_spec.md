# Team Data Interfaces & Contracts

This document defines the stable data structures and expected formats shared between the simulation module (Member 2), quantum solver (Member 1), classical solver (Member 4), and dashboard (Member 3).

---

## 1. Internal API Contracts (Python)

When integrating code within the `q_rescue` package, use the typed Python models directly. Do not pass JSON dictionaries or raw CSV paths between modules.

### Simulation → Solvers

The scenario generator (`q_rescue.simulation.scenarios`) outputs a `DisasterScenario` dataclass.

**Member 1 (Quantum):** Consumes `DisasterScenario` and `CostMatrix` via `AmbulanceAllocationQuboBuilder.build()`.
**Member 4 (Classical):** Consumes `scenario.ambulances` and `scenario.incidents` via `GreedyAllocator.solve()`.

### Solvers → Dashboard / Metrics

All solvers must return an `OptimizationResult` containing:
- `assignments: list[Assignment]`
- `objective_value: float`
- `solver_name: str`
- `feasible: bool`

**Member 3 (Dashboard):** Uses `q_rescue.services.response_service.compare_allocators()` which accepts a `DisasterScenario` and returns the metrics and `OptimizationResult` for both solvers.

---

## 2. External Exports (CSV & JSON)

For downstream analysis, debugging, or external tools, the simulation module exports raw datasets to `data/outputs/`.

### JSON Exports

#### `scenario.json`
Contains all entities, categories, and severity mappings in a single file. Useful for web dashboards.

#### `cost_matrix.json`
Nested dictionary of pre-computed costs: `{"ambulance_id": {"incident_id": cost}}`.

### CSV Exports

#### `ambulances.csv`
| id | lat | lon | status |
|---|---|---|---|
| A1 | 53.3851 | -1.4590 | Available |

#### `incidents.csv`
| id | lat | lon | severity_level | severity_weight | category |
|---|---|---|---|---|---|
| I1 | 53.4004 | -1.4754 | CRITICAL | 100 | flood |

#### `hospitals.csv`
| id | name | lat | lon | capacity | available_beds |
|---|---|---|---|---|---|
| H1 | Northern General Hospital | 53.4096 | -1.4565 | 1100 | 770 |

#### `cost_matrix.csv`
Rows = ambulances, Columns = incidents. Values = computed cost.

| ambulance_id | I1 | I2 | I3 |
|---|---|---|---|
| A1 | -31.97 | -15.97 | -23.95 |
