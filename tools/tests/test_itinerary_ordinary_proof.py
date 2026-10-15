"""The ordinary-mission journey must fail closed on missing evidence."""

import importlib.util
from pathlib import Path

import pytest

PATH = (
    Path(__file__).resolve().parents[1]
    / "acceptance/itinerary-planning/ordinary_proof.py"
)


def validator():
    spec = importlib.util.spec_from_file_location("ordinary_proof", PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_complete_proof_is_required_for_exact_candidate():
    module = validator()
    proof = {name: True for name in module.REQUIRED}
    proof["candidate_sha"] = "a" * 40
    assert module.validate(proof, "a" * 40)
    for field in module.REQUIRED:
        broken = proof.copy()
        broken[field] = False
        with pytest.raises(ValueError):
            module.validate(broken, "a" * 40)
        broken.pop(field)
        with pytest.raises(ValueError):
            module.validate(broken, "a" * 40)
    with pytest.raises(ValueError):
        module.validate(proof, "b" * 40)
