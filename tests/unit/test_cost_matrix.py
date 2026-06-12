import pytest
import pandas as pd
import numpy as np

from q_rescue.domain.models import Ambulance, Incident, Location, Severity, DisasterCategory
from q_rescue.simulation.generator import DisasterScenario
from q_rescue.simulation.cost_matrix import build_cost_matrix


@pytest.fixture
def sample_scenario():
    ambulances = [
        Ambulance("A1", Location(53.38, -1.47)),
        Ambulance("A2", Location(53.40, -1.45)),
    ]
    incidents = [
        Incident("I1", Location(53.39, -1.46), Severity.LOW),
        Incident("I2", Location(53.39, -1.46), Severity.CRITICAL),
    ]
    return DisasterScenario(
        name="Test",
        ambulances=ambulances,
        incidents=incidents,
        hospitals=[],
        category=DisasterCategory.GENERIC,
    )


def test_cost_matrix_dimensions(sample_scenario):
    cm = build_cost_matrix(sample_scenario)

    assert len(cm.ambulance_ids) == 2
    assert len(cm.incident_ids) == 2

    assert "A1" in cm.matrix
    assert "I1" in cm.matrix["A1"]


def test_severity_weighting_reduces_cost(sample_scenario):
    # I1 and I2 are at the exact same location, but I2 is Critical and I1 is Low
    cm = build_cost_matrix(sample_scenario, distance_weight=1.0, severity_weight=8.0)

    cost_a1_i1 = cm.matrix["A1"]["I1"]
    cost_a1_i2 = cm.matrix["A1"]["I2"]

    # Cost for Critical (I2) should be much lower (more negative) than Low (I1)
    # because the solver minimises cost.
    assert cost_a1_i2 < cost_a1_i1

    # The difference should be exactly (4 - 1) * 8.0 = 24.0
    assert pytest.approx(cost_a1_i1 - cost_a1_i2) == 24.0


def test_to_dataframe(sample_scenario):
    cm = build_cost_matrix(sample_scenario)
    df = cm.to_dataframe()

    assert isinstance(df, pd.DataFrame)
    assert list(df.index) == ["A1", "A2"]
    assert list(df.columns) == ["I1", "I2"]
    assert df.loc["A1", "I1"] == cm.matrix["A1"]["I1"]


def test_to_numpy(sample_scenario):
    cm = build_cost_matrix(sample_scenario)
    arr = cm.to_numpy()

    assert isinstance(arr, np.ndarray)
    assert arr.shape == (2, 2)
    assert arr[0, 0] == cm.matrix["A1"]["I1"]
    assert arr[1, 1] == cm.matrix["A2"]["I2"]
