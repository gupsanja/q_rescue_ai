# Ethical and Social Impact Discussion

## 1. Emergency-response risk

Q-Rescue AI is a high-consequence decision-support prototype. An incorrect
severity prediction or allocation can delay assistance, misallocate scarce
ambulances, or increase pressure on a hospital. The system therefore treats
AI output as a prioritisation signal rather than a guaranteed statement of
future casualties or need.

Safety controls in the implementation include:

- hard feasibility constraints remain active in the QUBO;
- the classical allocation baseline is retained for comparison;
- prediction confidence and class probabilities are exposed;
- invalid AI data is rejected at the integration boundary;
- large exact-QUBO runs are explicitly skipped;
- the dashboard labels the output as recommendation-only.

## 2. Data bias and representativeness

The prediction model is trained from a particular dataset and the simulation
generates synthetic Sheffield scenarios. Neither should be assumed to
represent every community, weather event, infrastructure condition or
population group.

Potential sources of bias include:

- under-representation of rare severe floods;
- historical reporting bias;
- differences between synthetic and real-world geography;
- population-density features acting as a proxy for other social factors;
- changes in climate, drainage infrastructure or emergency-service capacity.

The model should therefore be evaluated on geographically and temporally
representative validation data before operational use. Monitoring should compare
performance across event types and affected areas rather than relying only on
overall accuracy.

## 3. Limits of automation

The AI layer predicts flood severity and resource demand; it does not determine
medical treatment, casualty worth, or the legally correct emergency action.
Optimisation also cannot observe every real-world factor, including blocked
roads, ambulance crew condition, changing hazards, hospital diversion status or
new incidents that arrive after the optimisation run.

Consequently:

- AI predictions are advisory;
- optimisation is a snapshot and must be rerun when material conditions change;
- unavailable or invalid predictions must not be replaced with an invented
  model output;
- operational staff can override the recommendation.

## 4. Explainability

The system exposes the information needed to understand an allocation:

- incident severity;
- AI class probabilities and confidence;
- predicted resource demand;
- QUBO severity/demand overrides;
- ambulance-to-incident assignment;
- travel distance;
- coverage and critical-coverage metrics;
- solver name and feasibility status.

For an operational deployment, this should be extended with model-level
explanations (for example, feature contribution reports), model versioning,
calibration results and a human-readable reason for each high-priority
recommendation.

Explainability must not be confused with certainty: a transparent model can
still be wrong.

## 5. Human oversight

A human-in-the-loop boundary is mandatory for emergency use. The current
application service explicitly reports:

```json
{
  "human_oversight_required": true,
  "automated_decision_status": "recommendation_only"
}
```

An operational interface should require the authorised operator to:

1. review prediction confidence and known data-quality warnings;
2. compare the classical baseline with the quantum recommendation;
3. check current road, hospital and incident information;
4. accept, modify or reject the proposed allocation;
5. record the reason for any override.

The audit trail should retain the scenario inputs, model version, prediction
payload, QUBO patch, solver output, metrics and operator decision.

## 6. Accountability

Responsibility should remain with the emergency-response organisation and its
authorised decision makers. A model or optimiser must not become an opaque
substitute for professional judgement.

Before real deployment, the project would require:

- independent safety validation;
- data-governance and privacy review;
- bias and subgroup evaluation where appropriate;
- cybersecurity testing;
- model/version change control;
- incident reporting and rollback procedures;
- clear ownership for model, simulation, optimisation and operational data.

## Assessment position

The ethical position of Q-Rescue AI is therefore **decision support, not
autonomous dispatch**. The technical design preserves classical and human
fallbacks, validates AI-to-optimisation data, exposes uncertainty and prevents
invalid model output from silently driving a high-consequence allocation.
