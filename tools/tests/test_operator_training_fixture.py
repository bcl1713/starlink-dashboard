"""Nonproduction training roots and the existing Operator context seam."""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend/starlink-location"))
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


def test_prerequisites_seed_only_planned_requirements_and_reopen_without_replaying_writes(
    tmp_path,
):
    root = tmp_path / "private"
    scenario.mark_root(root)
    first = scenario.seed_prerequisites(root)
    second = scenario.seed_prerequisites(root)
    assert first["store_id"] == second["store_id"]
    assert first["api_epoch"] == second["api_epoch"]
    assert first["record_ids"] == second["record_ids"]
    assert first["H"] == second["H"]
    assert first["learner_actions_seeded"] is False
    assert len(first["leg_ids"]) == 2
    assert len(first["record_ids"]) >= 5
