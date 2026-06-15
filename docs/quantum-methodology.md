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

## QAOA workflow

Qiskit converts the binary QUBO into an equivalent Ising Hamiltonian whose
lowest-energy state represents the best assignment. QAOA prepares and samples
an approximate low-energy state by alternating two circuit layers:

1. The cost layer applies phases based on the QUBO/Ising objective.
2. The mixer layer rotates the qubits so the algorithm can explore other binary
   assignments.

For `p` QAOA repetitions, the circuit has `2p` trainable angles. A classical
COBYLA optimiser repeatedly updates those angles using sampled objective values.
The best measured bit string is translated back into ambulance/incident
assignment variables.

Initial POC configuration:

- QAOA repetitions (`reps`): 1
- Statevector sampler shots: 1024
- COBYLA maximum iterations: 100
- Random seed: 42
- Initial point: seeded non-zero angles in `[0, 2*pi)`, with length `2 * reps`

`StatevectorSampler` runs locally and samples from an ideal statevector. The
finite shot count still introduces sampling behaviour, but this is not a noisy
hardware experiment. Real-device execution and noise modelling are future work.

## Classical, exact, and QAOA comparison

All solvers must be evaluated on the same scenario and against the same QUBO.
The classical greedy allocator normally reports total travel distance, whereas
the quantum solvers report QUBO energy. These values are not directly
comparable. For a fair comparison, classical assignments are encoded as a
binary QUBO sample and evaluated with the same `Q(x)` equation.

The report keeps two categories of measurements separate:

- Operational metrics: average travel distance, incident coverage, critical
  coverage, assignment feasibility, and runtime.
- Optimisation metrics: QUBO energy and absolute/relative gap from the exact
  QUBO optimum.

Because valid QUBO energies can be negative, the relative gap is calculated as:

`100 * (solver_energy - exact_energy) / abs(exact_energy)`

This is reported as a percentage gap rather than as a conventional
approximation ratio, whose interpretation becomes confusing for negative
objectives.

### Week 1 POC results

Configuration: 3 ambulances, 5 incidents, 15 binary variables, grid coordinates,
seed 42, QAOA `reps=1`, 1024 shots, and COBYLA `maxiter=100`.

| Solver | QUBO energy | Runtime (local) | Average distance | Coverage | Critical coverage | Feasible |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Classical greedy | -68.643651 | 0.000015 s | 3.785 km | 60% | 100% | Yes |
| Exact enumeration | -68.643651 | 0.485534 s | 3.785 km | 60% | 100% | Yes |
| QAOA simulator | -31.075298 | 5.644261 s | 10.975 km | 60% | 50% | Yes |

The classical and exact solvers selected the same assignments: `A1->I1`,
`A2->I2`, and `A3->I4`. QAOA selected `A1->I4`, `A2->I2`, and `A3->I3`.
Its absolute energy gap was `37.568353`, or `54.73%` relative to the exact
energy magnitude.

This result validates that the QUBO can be executed through QAOA and decoded
into a feasible emergency allocation. It does not demonstrate quantum
advantage: at this shallow circuit depth, QAOA produced a lower-quality result
and took longer than both classical methods on the small simulator problem.
Future experiments should test more repetitions, optimisers, initial points,
and seeds, while reporting all attempted configurations rather than selecting
only the best run.

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
