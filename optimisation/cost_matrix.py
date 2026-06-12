from simulation.ambulances import GENERATED_AMBULANCES as ambulances
from simulation.incidents import GENERATED_INCIDENTS as incidents

cost_matrix = {}

for ambulance in ambulances:

    cost_matrix[ambulance["id"]] = {}

    for incident in incidents:

        distance = ...

        cost_matrix[
            ambulance["id"]
        ][
            incident["id"]
        ] = distance