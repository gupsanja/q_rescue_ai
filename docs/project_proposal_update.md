# Q-Rescue AI Project Proposal Update

## Purpose Of This Update

The original Q-Rescue AI proposal described a two-phase project:

1. Hackathon prototype: quantum/classical emergency response optimisation.
2. Post-hackathon extension: AI-powered disaster prediction feeding into the optimisation layer.

The hackathon phase is now complete. This document updates the project proposal
to show what was achieved during the hackathon and how the project should move
forward into the AI prediction phase.

## Updated Project Vision

Q-Rescue AI is an intelligent disaster response decision-support platform. The
system is designed to combine:

- disaster simulation,
- AI-based incident and demand prediction,
- classical and quantum-inspired optimisation,
- emergency response allocation,
- dashboard visualisation and result comparison.

The long-term workflow remains:

```text
AI Prediction
  -> Disaster Risk And Demand Assessment
  -> Resource Allocation Optimisation
  -> Emergency Response Recommendations
  -> UI Result Summary And Visualisation
```

## Hackathon Phase Completed

The 30 June hackathon focused on proving that emergency response allocation can
be modelled as an optimisation problem and compared across classical and
quantum-inspired approaches.

### Completed Hackathon Capabilities

- Disaster scenarios can be generated for Sheffield-based emergencies.
- Incidents, ambulances, hospitals, severity levels, and distance matrices are
  represented using shared project schemas.
- Classical allocation baselines were implemented.
- A QUBO formulation was implemented for ambulance-to-incident allocation.
- Qiskit/QAOA integration was validated on small scenarios.
- Exact enumeration was added for small-case correctness checking.
- Multi-start QAOA was added to reduce seed sensitivity.
- Medium and large benchmark modes were added.
- Hard critical-priority mode was added to improve coverage of critical
  incidents.
- Allocation result JSON was generated for UI integration.
- Documentation was created for methodology, demo flow, UI integration, and
  known limitations.

### Hackathon Outcome

The prototype successfully demonstrated the core optimisation workflow:

```text
Disaster Scenario
  -> Distance And Severity Inputs
  -> Classical Allocation
  -> QUBO / QAOA Allocation
  -> Metrics Comparison
  -> UI-Ready Allocation Result JSON
```

The project can now generate allocation results for small, medium, and large
benchmark scenarios. For small cases, exact enumeration and QAOA can be run
locally. For medium and large cases, exact enumeration and local QAOA are marked
as skipped when they exceed practical runtime limits.

### Important Hackathon Limitation

The project should not claim quantum advantage yet.

The hackathon work proves that the QUBO and QAOA pipeline works on small cases,
but further research, larger experiments, decomposition methods, real quantum
hardware testing, or quantum-inspired scalable solvers would be required before
making any claim of quantum advantage.

## Post-Hackathon Direction: AI Prediction Layer

The next major phase is to build the AI prediction layer described in the
original project proposal.

The purpose of this layer is to predict likely disaster impact before the
optimisation layer runs. The prediction output should become the input to the
existing simulation and allocation pipeline.

## AI Prediction Goals

The AI prediction layer should answer questions such as:

- How many incidents are likely to occur?
- Which areas are most likely to be affected?
- What severity levels are likely?
- How much pressure will ambulances and hospitals face?
- What resource demand should the optimiser prepare for?

## Recommended Prediction Features

### 1. Incident Demand Prediction

Predict the expected number of emergency incidents for a selected disaster type,
location, and time window.

Example output:

```json
{
  "predicted_incident_count": 20
}
```

### 2. Severity Prediction

Predict the likely severity distribution across incidents.

Example output:

```json
{
  "severity_distribution": {
    "LOW": 0.10,
    "MEDIUM": 0.25,
    "HIGH": 0.40,
    "CRITICAL": 0.25
  }
}
```

### 3. High-Risk Zone Prediction

Predict which Sheffield zones are likely to have higher emergency demand.

Example output:

```json
{
  "risk_zones": [
    {
      "zone_id": "sheffield_flood_zone_1",
      "risk_score": 0.87
    }
  ]
}
```

### 4. Resource Pressure Prediction

Estimate whether ambulance availability or hospital capacity may become
strained.

Example output:

```json
{
  "ambulance_pressure": "high",
  "hospital_pressure": "medium"
}
```

## AI Prediction Inputs

The first version can use synthetic or semi-realistic inputs:

- disaster category,
- location or Sheffield zone,
- time of day,
- day of week,
- weather/rainfall indicator,
- flood or industrial risk indicator,
- available ambulances,
- hospital capacity,
- historical or simulated incident count.

If real historical datasets become available later, the same interface can be
kept while replacing synthetic training data with real data.

## Recommended First AI Models

The first AI prediction prototype should use explainable, lightweight models:

- Random Forest Regressor for predicted incident count.
- Random Forest Classifier for severity level prediction.
- Optional Poisson Regressor for count-based emergency demand.

These models are recommended because they are easier to explain, easier to
train, and suitable for a project extension before moving to deep learning.

Future versions can explore:

- XGBoost,
- LSTM forecasting,
- transformer-based forecasting,
- graph-based spatial prediction,
- real-time weather or sensor data integration.

## Integration With Existing Optimisation Pipeline

The AI prediction layer should not replace the optimisation layer. It should
generate better inputs for it.

Recommended flow:

```text
UI Disaster Input
  -> AI Prediction Model
  -> Predicted Incident Count, Severity Mix, And Risk Zones
  -> DisasterScenario Generation
  -> Classical / Quantum Allocation
  -> allocation_result JSON
  -> UI Display
```

The existing allocation interface can remain stable:

```python
from q_rescue.services.allocation_output import build_allocation_output_from_request

allocation_result = build_allocation_output_from_request(request)
```

The AI layer should eventually create or enrich the `request` passed into this
function.

## Proposed New Project Structure

The AI prediction phase can add the following documentation and code structure:

```text
src/q_rescue/prediction/
  __init__.py
  features.py
  models.py
  predictor.py
  synthetic_training_data.py
  prediction_output.py

scripts/
  train_prediction_model.py
  run_prediction_demo.py

data/prediction/
  training_data.csv
  model.joblib
  prediction_result.json

docs/
  ai_prediction_plan.md
```

## Suggested AI Prediction Deliverables

The next phase should aim to deliver:

- AI prediction design document.
- Synthetic training dataset for disaster prediction.
- Baseline incident count prediction model.
- Baseline severity prediction model.
- Prediction result JSON schema.
- Integration path from prediction output to allocation input.
- Demo showing predicted incidents feeding into allocation.

## Updated Success Criteria

The next version of Q-Rescue AI should be considered successful if it can:

- accept a disaster type and basic context from the UI,
- predict likely incident demand,
- predict severity distribution or severity per generated incident,
- generate a scenario from prediction results,
- run the existing allocation pipeline on that scenario,
- return UI-ready allocation results,
- clearly explain prediction confidence and limitations.

## Notes For Task Distribution

Task distribution is intentionally not assigned in this document.

Member 2 can use this updated proposal as the basis for dividing the AI
prediction phase into team responsibilities.

Recommended workstreams to distribute:

- data and feature design,
- model training and evaluation,
- prediction-to-simulation integration,
- UI prediction input and output display,
- documentation and validation.
