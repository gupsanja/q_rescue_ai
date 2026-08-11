# System Architecture

## Runtime flow

1. The simulation module produces a `DisasterScenario`, distance matrix,
   severity mapping and (for flood scenarios) hydrological observations.
2. The shared application service validates integration inputs and orchestrates
   the workflow.
3. The AI Prediction API validates observations, runs the existing XGBoost
   predictor, and owns the prediction → QUBO patch → dashboard prediction
   contracts.
4. The classical baseline runs first and remains an interpretable fallback.
5. The quantum QUBO consumes the same simulation inputs and, when available,
   the validated AI patch. Feasibility constraints are unchanged.
6. Classical and quantum outputs are evaluated by the common metrics module.
7. The application service returns one JSON-compatible dashboard payload.

## Ownership boundaries

| Area | Owner | Public contract |
| --- | --- | --- |
| Simulation | Member 2 | `DisasterScenario`, `DistanceMatrix`, `SeverityMapping` |
| AI prediction | Member 5 | `PredictionAPI`, `AIPrediction`, `QuboAIPatch`, dashboard prediction payload |
| Quantum optimisation | Member 1 | `AmbulanceAllocationQuboBuilder`, `QuantumAllocator` |
| Classical baseline | Member 4 | `GreedyAllocator`, `OptimalAssignmentAllocator` |
| Metrics | Shared integration | `calculate_metrics(OptimizationResult, incidents)` |
| Application integration | Member 4 | `run_application_workflow()` |
| Dashboard | Member 3 | unified application/dashboard payload |

## Integration boundary

`src/q_rescue/services/application_service.py` is the composition boundary.
It does not duplicate simulation, prediction, optimisation or metric algorithms.
It passes their existing typed objects between modules and serialises the final
result into a stable dashboard contract.

See [`docs/integration_boundaries.md`](integration_boundaries.md) for the
request/response contracts, validation rules and ownership details.

## Safety boundary

AI and optimisation are recommendation layers. The application explicitly
reports `human_oversight_required=true` and
`automated_decision_status=recommendation_only`. Invalid AI data is rejected;
it is not silently converted into a fabricated prediction.
