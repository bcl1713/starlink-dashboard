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


def test_real_records_acknowledgments_and_receipts_share_fixture_namespace_across_segments(
    tmp_path, monkeypatch
):
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from uuid import uuid4
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.operator import router
    from app.mission import storage
    from app.operator.runtime import OperatorRuntimeBinding

    root = tmp_path / "learner"
    scenario.mark_root(root)
    seeded = scenario.seed_prerequisites(root)
    monkeypatch.setattr(storage, "MISSIONS_DIR", root / "missions")
    monkeypatch.setenv("OPERATOR_ROOT", str(root / "operator"))
    monkeypatch.setenv("OPERATOR_ENABLED", "true")
    current = ["simulation", None]
    clock = SimpleNamespace(
        now=lambda: datetime(2026, 10, 17, 16, tzinfo=timezone.utc),
        monotonic=lambda: 0.0,
    )
    binding = OperatorRuntimeBinding(
        clock=clock, context=scenario.stable_context(root, lambda: tuple(current))
    )
    app = FastAPI()
    app.state.operator_binding = binding
    app.include_router(router)
    ids = []
    bindings = [binding]
    try:
        with TestClient(app) as client:
            for index, segment in enumerate(
                (None, "actual-first-leg", "actual-second-leg")
            ):
                current[1] = segment
                health = client.get("/api/v2/operator/health").json()
                assert health["store_id"] == seeded["store_id"]
                assert health["api_epoch"] == seeded["api_epoch"]
                headers = {
                    "Idempotency-Key": str(uuid4()),
                    "X-Operator-Store-Epoch": health["api_epoch"],
                }
                body = {
                    "schema_version": 1,
                    "record_type": "journal_entry",
                    "mission_id": seeded["mission_id"],
                    "scope": "preflight" if index == 0 else "leg",
                    "leg_id": None if index == 0 else seeded["leg_ids"][index - 1],
                    "time": {
                        "occurred_at": None,
                        "ended_at": None,
                        "precision": "unknown",
                        "end_state": "unknown",
                        "planned_start_at": None,
                        "planned_end_at": None,
                    },
                    "payload": {
                        "schema_version": 1,
                        "entry_type": "note",
                        "title": f"Learner stage {index}",
                        "note": "Actual test action, not seeded",
                        "previous_leg_id": None,
                        "next_leg_id": None,
                    },
                }
                saved = client.post(
                    "/api/v2/operator/records", json=body, headers=headers
                )
                assert saved.status_code == 201, saved.text
                receipt = saved.json()
                assert (
                    client.post(
                        "/api/v2/operator/records", json=body, headers=headers
                    ).json()
                    == receipt
                )
                ids.append(receipt["saved_records"][0]["record_id"])
                feed = client.get(
                    "/api/v2/operator/events",
                    params={"mission_id": seeded["mission_id"]},
                ).json()
                event = next(
                    event
                    for event in feed["events"]
                    if event["notification"]["acknowledgment_available"]
                    and not event["notification"]["acknowledged"]
                )
                acknowledgment = {
                    "schema_version": 1,
                    "occurrence_id": event["notification"]["generation"],
                    "severity_generation": event["notification"]["severity_generation"],
                    "snapshot_token": feed["snapshot_token"],
                }
                result = client.post(
                    "/api/v2/operator/events/acknowledge",
                    json=acknowledgment,
                    headers={**headers, "Idempotency-Key": str(uuid4())},
                )
                assert result.status_code == 200, result.text
        binding.close()
        reopened = OperatorRuntimeBinding(
            clock=clock, context=scenario.stable_context(root, lambda: tuple(current))
        )
        bindings.append(reopened)
        with reopened.access() as runtime:
            assert str(runtime.health().store_id) == seeded["store_id"]
            with runtime.service.store.connect() as db:
                assert (
                    db.execute("SELECT count(*) FROM event_acknowledgments").fetchone()[
                        0
                    ]
                    == 3
                )
                assert (
                    db.execute("SELECT count(*) FROM revisions").fetchone()[0]
                    == len(seeded["record_ids"]) + 3
                )
        reopened.close()
        normal = OperatorRuntimeBinding(clock=clock, context=lambda: tuple(current))
        bindings.append(normal)
        with normal.access() as runtime:
            assert runtime.health().simulation_run_id == "actual-second-leg"
            assert not runtime.health().ready
        normal.close()
    finally:
        for owned in bindings:
            owned.close()
