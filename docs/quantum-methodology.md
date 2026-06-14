# Quantum Methodology

## Decision variables

Let `x[a,i]` be 1 when ambulance `a` is assigned to incident `i`, otherwise 0.

## Initial POC objective

Minimise a weighted combination of travel distance and negative severity reward:

`C(x) = sum((w_d * distance[a,i] - w_s * severity[i]) * x[a,i])`

Let `K = min(number of ambulances, number of incidents)`. The assignment-count
penalty is:

`P_count(x) = lambda * (K - sum(x[a,i]))^2`

This prevents the optimiser from returning an artificially cheap solution that
leaves usable ambulances idle. For binary variables, `x^2 = x`, so this square
can be expanded directly into linear and quadratic QUBO coefficients.

Add collision penalties when:

- one ambulance is assigned to more than one incident;
- one incident receives more than one ambulance.

For every conflicting variable pair `(x_p, x_q)`:

`P_collision(x) = lambda * x_p * x_q`

The complete POC QUBO is:

`Q(x) = C(x) + P_count(x) + P_collision(x)`

The solver minimises `Q(x)`. Lower travel distance lowers the score, higher
severity lowers the score through its reward, and invalid assignments increase
the score through penalties.

## Assumptions for the first POC

- Each ambulance serves at most one incident during one decision window.
- Each incident receives at most one ambulance.
- The model creates exactly `K` assignments when both input sets are non-empty.
- Severity is represented as `LOW=1`, `MEDIUM=2`, `HIGH=3`, `CRITICAL=4`.
- Travel distance is Euclidean for the synthetic scenario.
- Hospital capacity and routing are deferred until the ambulance model is stable.

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
