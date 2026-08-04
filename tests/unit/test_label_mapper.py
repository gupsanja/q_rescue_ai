import pytest

from q_rescue.ai.label_mapper import (
    AI_LABEL_TO_INT,
    CanonicalSeverityEncoder,
    ai_label_to_severity,
    ai_label_to_weight,
)
from q_rescue.domain.models import Severity

def test_ai_label_to_severity():
    assert ai_label_to_severity("Low") == Severity.LOW
    assert ai_label_to_severity("Moderate") == Severity.MEDIUM
    assert ai_label_to_severity("High") == Severity.HIGH
    assert ai_label_to_severity("Severe") == Severity.CRITICAL
    
    with pytest.raises(KeyError):
        ai_label_to_severity("Unknown")

def test_ai_label_to_weight():
    assert ai_label_to_weight("Low") == 25
    assert ai_label_to_weight("Moderate") == 50
    assert ai_label_to_weight("High") == 75
    assert ai_label_to_weight("Severe") == 100
    
    with pytest.raises(KeyError):
        ai_label_to_weight("Unknown")

def test_canonical_severity_encoder():
    encoder = CanonicalSeverityEncoder()
    
    # Test transform
    labels = ["High", "Low", "Severe", "Moderate"]
    encoded = encoder.transform(labels)
    
    expected = [AI_LABEL_TO_INT[l] for l in labels]
    assert list(encoded) == expected
    
    # Test inverse transform
    decoded = encoder.inverse_transform(encoded)
    assert decoded == labels
