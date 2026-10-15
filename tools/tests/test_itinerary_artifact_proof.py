"""Export qualification rejects divergent canonical CSV intervals."""

import importlib.util
from pathlib import Path

import pytest


def test_csv_intervals_must_match_canonical_evaluation():
    path = (
        Path(__file__).resolve().parents[1]
        / "acceptance/itinerary-planning/artifact_proof.py"
    )
    spec = importlib.util.spec_from_file_location("artifact_proof", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(ValueError, match="CSV"):
        module.check_csv('Metadata\n"{}"\n', [{"start_time": "2035-01-01T10:00:00Z"}])
