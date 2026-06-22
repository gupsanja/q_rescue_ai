from __future__ import annotations

import argparse
from pathlib import Path

from q_rescue.quantum.comparison import (
    ComparisonReport,
    SolverBenchmark,
    compare_benchmark_exports,
    compare_solvers,
)
from q_rescue.quantum.qaoa_solver import MultiStartQAOASolver, QiskitQAOASolver
from q_rescue.simulation.generator import generate_scenario


def main() -> None:
    args = _parse_args()
    qaoa_solver = _build_qaoa_solver(args)

    if args.benchmark_dir:
        report = compare_benchmark_exports(
            args.benchmark_dir,
            qaoa_solver=qaoa_solver,
            run_exact=not args.skip_exact,
            run_qaoa=not args.skip_qaoa,
        )
    else:
        scenario = generate_scenario(
            ambulance_count=args.ambulances,
            incident_count=args.incidents,
            seed=args.seed,
            use_sheffield_coords=False,
        )
        report = compare_solvers(
            scenario,
            qaoa_solver=qaoa_solver,
            run_exact=not args.skip_exact,
            run_qaoa=not args.skip_qaoa,
        )
    _print_report(report)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Q-Rescue allocation solvers")
    parser.add_argument("--ambulances", type=int, default=3)
    parser.add_argument("--incidents", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--reps", type=int, default=1)
    parser.add_argument("--shots", type=int, default=1024)
    parser.add_argument("--maxiter", type=int, default=100)
    parser.add_argument(
        "--qaoa-attempts",
        type=int,
        default=4,
        help="Number of deterministic QAOA starts to try before keeping the best solution",
    )
    parser.add_argument(
        "--benchmark-dir",
        type=Path,
        help="Directory containing Member 2 benchmark JSON exports",
    )
    parser.add_argument(
        "--skip-exact",
        action="store_true",
        help="Skip exact enumeration for benchmarks above the 24-variable exact limit",
    )
    parser.add_argument(
        "--skip-qaoa",
        action="store_true",
        help="Skip local QAOA simulation for benchmarks too large for statevector sampling",
    )
    return parser.parse_args()


def _build_qaoa_solver(args: argparse.Namespace) -> QiskitQAOASolver | MultiStartQAOASolver:
    if args.qaoa_attempts == 1:
        return QiskitQAOASolver(
            reps=args.reps,
            shots=args.shots,
            seed=args.seed,
            maxiter=args.maxiter,
        )
    return MultiStartQAOASolver(
        reps=args.reps,
        shots=args.shots,
        seed=args.seed,
        maxiter=args.maxiter,
        attempts=args.qaoa_attempts,
    )


def _print_report(report: ComparisonReport) -> None:
    print(f"Scenario: {report.scenario_name}")
    print(f"Binary variables: {report.binary_variables}")
    print()
    print(
        f"{'Solver':<20} {'QUBO energy':>12} {'Runtime (s)':>12} "
        f"{'Avg distance':>14} {'Coverage':>10} {'Critical':>10} {'Feasible':>10}"
    )
    print("-" * 104)
    _print_benchmark(report.classical)
    if report.exact is None:
        print(
            f"{'exact-enumeration':<20} {'N/A':>12} {'N/A':>12} {'N/A':>14} {'N/A':>10} {'N/A':>10} {'N/A':>10}"
        )
    else:
        _print_benchmark(report.exact)
    if report.qaoa is None:
        print(
            f"{'qiskit-qaoa':<20} {'N/A':>12} {'N/A':>12} {'N/A':>14} "
            f"{'N/A':>10} {'N/A':>10} {'N/A':>10}"
        )
    else:
        _print_benchmark(report.qaoa)

    print()
    if report.exact is None:
        print("Classical gap from exact: N/A (exact enumeration skipped)")
        print("QAOA gap from exact: N/A (exact enumeration skipped)")
    else:
        print(
            f"Classical gap from exact: {report.classical_gap:.6f} "
            f"({report.classical_relative_gap_percent:.2f}%)"
        )
        print(
            f"QAOA gap from exact: {report.qaoa_gap:.6f} ({report.qaoa_relative_gap_percent:.2f}%)"
        )

    benchmarks = [report.classical]
    if report.exact is not None:
        benchmarks.append(report.exact)
    if report.qaoa is not None:
        benchmarks.append(report.qaoa)
    for benchmark in benchmarks:
        assignments = ", ".join(
            f"{item.ambulance_id}->{item.incident_id}" for item in benchmark.assignments
        )
        print(f"{benchmark.solver_name} assignments: {assignments}")


def _print_benchmark(benchmark: SolverBenchmark) -> None:
    metrics = benchmark.metrics
    print(
        f"{benchmark.solver_name:<20} {benchmark.qubo_energy:>12.6f} "
        f"{benchmark.runtime_seconds:>12.6f} {metrics['average_distance_km']:>14.3f} "
        f"{metrics['coverage_percent']:>9.1f}% "
        f"{metrics['critical_coverage_percent']:>9.1f}% "
        f"{str(benchmark.feasible):>10}"
    )


if __name__ == "__main__":
    main()
