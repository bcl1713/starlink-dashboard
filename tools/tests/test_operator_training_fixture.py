"""Nonproduction training roots and the existing Operator context seam."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "operator_training_scenario", ROOT / "tools/training/operator-mission/scenario.py"
)
scenario = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scenario)


def test_root_requires_explicit_marker_and_simulation(tmp_path):
    root = tmp_path / "private-training"
    with pytest.raises(ValueError, match="marked"):
        scenario.training_namespace(root, mode="simulation")
    manifest = scenario.mark_root(root)
    assert scenario.training_namespace(root, mode="simulation") == manifest["namespace"]
    with pytest.raises(ValueError, match="simulation"):
        scenario.training_namespace(root, mode="live")


def test_never_adopts_nonempty_or_symlink_root(tmp_path):
    existing = tmp_path / "existing"
    existing.mkdir()
    (existing / "operations.sqlite3").write_bytes(b"preserve operational bytes")
    with pytest.raises(ValueError, match="empty"):
        scenario.mark_root(existing)
    link = tmp_path / "link"
    link.symlink_to(existing, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        scenario.mark_root(link)
    assert (
        existing / "operations.sqlite3"
    ).read_bytes() == b"preserve operational bytes"


def test_fixture_context_is_stable_across_actual_replay_segments_and_restart(tmp_path):
    root = tmp_path / "learner"
    manifest = scenario.mark_root(root)
    current = ["simulation", None]
    context = scenario.stable_context(root, lambda: tuple(current))
    assert context() == ("simulation", manifest["namespace"])
    current[1] = "actual-leg-one-run"
    assert context() == ("simulation", manifest["namespace"])
    current[1] = "actual-leg-two-run"
    assert scenario.stable_context(root, lambda: tuple(current))() == context()
    current[0] = "live"
    with pytest.raises(ValueError, match="simulation"):
        context()
