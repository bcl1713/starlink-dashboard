"""Explicit first-use provisioning must never reset an existing namespace."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.operator import router
from app.operator.errors import OperatorError
from app.operator.runtime import OperatorRuntime, OperatorRuntimeBinding
from app.operator.settings import OperatorSettings


@pytest.mark.parametrize("mode,run", [("live", None), ("simulation", "first-run")])
def test_fresh_namespace_requires_explicit_provision_and_survives_restart(
    tmp_path, clock, mode, run
):
    settings = OperatorSettings(
        enabled=True,
        root=tmp_path / "operator",
        source_mode=mode,
        simulation_run_id=run,
    )
    runtime = OperatorRuntime.start(settings, clock=clock)
    assert runtime.health().error_code == "store_initialization_required"
    assert not settings.database_path.parent.exists()
    first = runtime.provision(expected_mode=mode, expected_run=run)
    assert first.ready
    assert (
        runtime.provision(expected_mode=mode, expected_run=run).store_id
        == first.store_id
    )
    runtime.close()
    reopened = OperatorRuntime.start(settings, clock=clock)
    assert reopened.health().store_id == first.store_id
    assert reopened.health().api_epoch == first.api_epoch
    reopened.close()


@pytest.mark.parametrize(
    "artifact",
    [
        "operations.sqlite3",
        "operations.identity.json",
        "operations.lock",
        "operations.sqlite3-wal",
        "backups",
    ],
)
def test_existing_artifact_is_recovery_not_first_use_and_is_never_overwritten(
    tmp_path, clock, artifact
):
    root = tmp_path / "operator"
    root.mkdir()
    path = root / artifact
    path.write_bytes(b"preserve this artifact")
    settings = OperatorSettings(enabled=True, root=root)
    runtime = OperatorRuntime.start(settings, clock=clock)
    assert runtime.health().error_code == "store_recovery_required"
    with pytest.raises(OperatorError):
        runtime.provision(expected_mode="live", expected_run=None)
    assert path.read_bytes() == b"preserve this artifact"
    assert (
        not (root / "operations.identity.json").exists()
        or artifact == "operations.identity.json"
    )
    runtime.close()


def test_wrong_context_does_not_create_a_namespace(tmp_path, clock):
    settings = OperatorSettings(
        enabled=True,
        root=tmp_path / "operator",
        source_mode="simulation",
        simulation_run_id="active-run",
    )
    runtime = OperatorRuntime.start(settings, clock=clock)
    with pytest.raises(OperatorError, match="store_context_changed"):
        runtime.provision(expected_mode="simulation", expected_run="previous-run")
    assert not settings.root.exists()


def test_live_and_simulation_runs_remain_separate_and_return_to_original_identity(
    tmp_path, clock, monkeypatch
):
    monkeypatch.setenv("OPERATOR_ENABLED", "true")
    monkeypatch.setenv("OPERATOR_ROOT", str(tmp_path / "operator"))
    context = ["simulation", "run-a"]
    binding = OperatorRuntimeBinding(clock=clock, context=lambda: tuple(context))
    identities = {}
    for mode, run in [("simulation", "run-a"), ("simulation", "run-b"), ("live", None)]:
        context[:] = [mode, run]
        with binding.access() as runtime:
            assert not runtime.health().ready
            identities[(mode, run)] = runtime.provision(
                expected_mode=mode, expected_run=run
            ).store_id
    assert len(set(identities.values())) == 3
    context[:] = ["simulation", "run-a"]
    with binding.access() as runtime:
        assert runtime.health().store_id == identities[("simulation", "run-a")]
    binding.close()


def test_provision_api_is_explicit_context_bound_and_disabled_feature_stays_disabled(
    tmp_path, clock, monkeypatch
):
    monkeypatch.setenv("OPERATOR_ENABLED", "true")
    monkeypatch.setenv("OPERATOR_ROOT", str(tmp_path / "operator"))
    app = FastAPI()
    binding = OperatorRuntimeBinding(
        clock=clock, context=lambda: ("simulation", "actual-run")
    )
    app.state.operator_binding = binding
    app.include_router(router)
    with TestClient(app) as client:
        missing = client.get("/api/v2/operator/health")
        assert missing.status_code == 503
        assert missing.json()["error_code"] == "store_initialization_required"
        wrong = client.post(
            "/api/v2/operator/provision",
            json={
                "schema_version": 1,
                "expected_source_mode": "simulation",
                "expected_simulation_run_id": "old-run",
            },
        )
        assert wrong.status_code == 409
        assert not (tmp_path / "operator").exists()
        result = client.post(
            "/api/v2/operator/provision",
            json={
                "schema_version": 1,
                "expected_source_mode": "simulation",
                "expected_simulation_run_id": "actual-run",
            },
        )
        assert result.status_code == 200
        assert result.json()["ready"]
        assert (
            client.get("/api/v2/operator/health").json()["store_id"]
            == result.json()["store_id"]
        )
        monkeypatch.setenv("OPERATOR_ENABLED", "false")
        assert client.post("/api/v2/operator/provision", json={}).status_code == 404
    binding.close()
