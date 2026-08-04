# Phase 2 Member 1: AI-To-QUBO Integration

## Owner

Member 1: Quantum Algorithm & QUBO Implementation Lead

## Purpose

Phase 2 adds an AI prediction layer before the optimisation layer. Member 1's
responsibility is to make sure the existing QUBO/QAOA allocation workflow can
consume AI-predicted incident severity and demand without changing the ownership
boundaries of the rest of the system.

The AI layer does not replace the QUBO. It produces prediction values that are
converted into QUBO weights.

```text
M2 scenario
  -> M5 AI predictions
  -> QUBO AI patch
  -> M1 QUBO builder
  -> quantum/classical allocation comparison
```

## AI Patch Contract

The QUBO builder accepts AI prediction data through:

```python
patched_builder = builder.apply_ai_patch(qubo_patch)
```

Expected patch shape:

```json
{
  "scenario_id": "sheffield_flood_response_seed_42",
  "model_version": "xgb_severity_v1",
  "severity_overrides": {
    "I1": 25,
    "I2": 75,
    "I3": 100
  },
  "demand_overrides": {
    "I1": 0.32,
    "I2": 0.71,
    "I3": 0.92
  }
}
```

## How Predicted Severity Is Used

`severity_overrides` replaces the incident's existing severity weight for QUBO
construction.

Example:

```text
Simulated severity for I3: LOW = 25
AI-predicted severity for I3: Severe = 100
QUBO severity used for I3: 100
```

This keeps the Phase 1 severity scale:

| AI label | Domain severity | QUBO weight |
| --- | --- | ---: |
| Low | LOW | 25 |
| Moderate | MEDIUM | 50 |
| High | HIGH | 75 |
| Severe | CRITICAL | 100 |

## How Predicted Demand Is Used

`demand_overrides` is a normalised value between `0.0` and `1.0`.

In the QUBO objective, predicted demand acts as an urgency bonus. Higher
predicted demand lowers the assignment cost, making the incident more attractive
to the optimiser.

This is intentionally not implemented as a distance multiplier. A distance
multiplier can make low-demand incidents appear cheaper and therefore more
attractive, which is the opposite of the intended Phase 2 behaviour.

## Updated QUBO Objective

For each ambulance `a` and incident `i`, the Phase 2 AI-aware assignment cost is:

```text
cost(a, i)
  = distance_weight * distance(a, i)
    - severity_weight * severity_normalised(i)
    - demand_weight * predicted_demand(i)
```

Where:

```text
severity_normalised(i) = severity_weight_from_schema(i) / 100
predicted_demand(i)    = value from demand_overrides, in range 0.0 to 1.0
```

Interpretation:

- shorter travel distance reduces response cost,
- higher predicted severity increases priority,
- higher predicted demand increases urgency,
- QUBO penalties still enforce valid assignments.

## Feasibility Constraints Remain Unchanged

The AI patch only changes linear assignment costs. It does not remove or weaken
the Phase 1 QUBO constraints:

- each ambulance can be assigned to at most one incident,
- each incident can receive at most one ambulance,
- the model assigns up to `min(number_of_ambulances, number_of_incidents)`,
- optional hard critical-priority mode still works with AI-predicted severity.

## Validation Completed

Member 1 validation now covers:

- AI severity overrides replace simulated severity weights.
- AI demand adds a priority bonus.
- Higher predicted demand is preferred when distance and severity are equal.
- An AI-patched QUBO can be solved with exact enumeration and still returns a
  feasible assignment.
- The AI-urgent incident is selected in a small validation case.

Validation command:

```bash
.venv/bin/pytest tests/unit/test_qubo_ai_patch.py tests/unit/test_qubo.py tests/unit/test_comparison.py
```

Latest focused result:

```text
19 passed
```

## Member Boundary Notes

Member 1 owns:

- `src/q_rescue/quantum/qubo.py`
- QUBO/QAOA behaviour
- QUBO-specific validation tests
- quantum methodology documentation

Member 1 does not own:

- AI model training,
- XGBoost prediction internals,
- hydrological feature generation,
- dashboard prediction display,
- API orchestration.

If issues are found in those areas, they should be raised with the relevant
team member rather than patched inside Member 1's task work.
