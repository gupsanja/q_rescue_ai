# Quantum Methodology

## Decision variables

Let `x[a,i]` be 1 when ambulance `a` is assigned to incident `i`, otherwise 0.

## Initial POC objective

Minimise a weighted combination of travel distance and negative severity reward:

`sum((distance_weight * distance[a,i] - severity_weight * severity[i]) * x[a,i])`

Add pairwise penalties when:

- one ambulance is assigned to more than one incident;
- one incident receives more than one ambulance.

## Member 1 validation checklist

- Confirm penalty weights dominate invalid low-distance solutions.
- Confirm critical incidents are preferred when resources are scarce.
- Compare exact QUBO and QAOA objective values on 3 ambulances / 5 incidents.
- Record QAOA reps, optimiser, shots, simulator backend, seed, and runtime.
- Report feasibility separately from objective quality.
- Explain scaling limits as binary variables grow by ambulances x incidents.

## Next modelling decisions

Hospital assignment, capacity, response-time thresholds, and mandatory coverage
should be added only after the ambulance POC is stable. They can be represented
with additional variables or a staged optimisation pipeline.

