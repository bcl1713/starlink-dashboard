"""Policy tuning validates real thresholds rather than trusting arbitrary env text."""

import pytest
from pydantic import ValidationError


def test_rapid_crossing_policy_can_be_injected(monkeypatch):
    from app.operator.event_policy import EventPolicy

    monkeypatch.setenv("OPERATOR_EVENT_MODEL_SHIFT_SECONDS", "20")
    monkeypatch.setenv("OPERATOR_EVENT_MODEL_CAPTURE_SPACING_SECONDS", "1")
    policy = EventPolicy.from_env()
    assert policy.model_shift_seconds == 20
    assert policy.model_capture_spacing_seconds == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("model_shift_seconds", 0),
        ("model_shift_seconds", float("nan")),
        ("model_capture_spacing_seconds", float("inf")),
        ("model_stable_captures", 1),
        ("model_escalation_captures", True),
    ],
)
def test_invalid_policy_is_rejected(field, value):
    from app.operator.event_policy import EventPolicy

    with pytest.raises(ValidationError):
        EventPolicy(**{field: value})
