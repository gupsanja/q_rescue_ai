from q_rescue.classical.allocator import GreedyAllocator
from q_rescue.metrics.evaluator import calculate_metrics
from q_rescue.quantum.optimizer import QuantumAllocator
from q_rescue.simulation.generator import DisasterScenario


def compare_allocators(scenario: DisasterScenario) -> dict[str, dict[str, object]]:
    """Application service consumed by scripts, tests, and the dashboard."""
    results = {
        "classical": GreedyAllocator().solve(scenario.ambulances, scenario.incidents),
        "quantum": QuantumAllocator().solve(scenario.ambulances, scenario.incidents),
    }
    return {
        name: {"result": result, "metrics": calculate_metrics(result, scenario.incidents)}
        for name, result in results.items()
    }

