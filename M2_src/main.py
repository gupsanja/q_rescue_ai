from simulation.scenarios import generate_scenario
from optimisation.cost_matrix import build_cost_matrix
from outputs.save_outputs import save_outputs

scenario = generate_scenario()

cost_matrix = build_cost_matrix(
    scenario
)

save_outputs(
    scenario,
    cost_matrix
)