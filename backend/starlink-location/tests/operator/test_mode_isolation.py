"""Restart, mode mismatch and unavailable optional sources never rewrite history."""

from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

from app.mission import storage
from app.operator.models import RecordFilter
from app.operator.provenance import SourceProvenance, SourceReference
from app.operator.read_metadata import freshness
from app.operator.runtime import OperatorRuntime
from app.operator.settings import OperatorSettings
from app.services.position_freshness import OBSERVATION_FRESHNESS_SECONDS
from tests.operator.fixtures import ScenarioClock, make_demo, seed_demo


def test_mode_restart_and_optional_provider(tmp_path, monkeypatch):
    clock = ScenarioClock()
    first = seed_demo(tmp_path, clock=clock, mode="simulation")
    assert seed_demo(tmp_path, clock=ScenarioClock(), mode="simulation") == first
    demo = make_demo(clock)
    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path / "missions")
    settings = OperatorSettings(
        enabled=True,
        root=tmp_path / "operator",
        source_mode="simulation",
        simulation_run_id=demo["run_id"],
    )
    wrong = OperatorRuntime.start(
        replace(
            settings,
            root=settings.database_path.parent,
            source_mode="live",
            simulation_run_id=None,
        ),
        clock=clock,
    )
    assert not wrong.health().ready and wrong.service is None
    assert wrong.health().error_code == "store_mode_mismatch"
    wrong.close()
    runtime = OperatorRuntime.start(settings, clock=clock)
    try:

        def unavailable(*args, **kwargs):
            raise ConnectionError("Synthetic optional provider unreachable")

        monkeypatch.setattr("httpx.Client.request", unavailable)
        runtime.freshness_policies["accepted_position"] = OBSERVATION_FRESHNESS_SECONDS
        clock.advance(60)
        assert seed_demo(tmp_path, clock=clock, mode="simulation") == first
        command = demo["commands"][0].model_copy(deep=True)
        command.payload.note = (
            "Synthetic optional source unavailable; local write survives"
        )
        saved = runtime.service.execute(
            command, key=str(uuid4()), epoch=first["epoch"]
        ).saved_records[0]
        assert saved.recorded_at == clock.now()
        source_time = clock.now() - timedelta(seconds=60)
        observed = saved.model_copy(
            update={
                "provenance": SourceProvenance(
                    kind="observed",
                    source_mode="simulation",
                    observed_at=source_time,
                    source_ref=SourceReference(producer_id="accepted_position"),
                )
            }
        )
        assert observed.provenance.observed_at != saved.recorded_at
        assert (
            freshness(observed, as_of=clock.now(), policies=runtime.freshness_policies)[
                "status"
            ]
            == "stale"
        )
        modeled = saved.model_copy(
            update={
                "provenance": SourceProvenance(
                    kind="modeled",
                    source_mode="simulation",
                    predicted_at=clock.now() - timedelta(seconds=30),
                    source_ref=SourceReference(producer_id="mission_pop_forecast"),
                )
            }
        )
        assert (
            freshness(modeled, as_of=clock.now(), policies=runtime.freshness_policies)[
                "status"
            ]
            == "unknown"
        )
        assert (
            freshness(saved, as_of=clock.now(), policies=runtime.freshness_policies)[
                "status"
            ]
            == "unknown"
        )
        page = runtime.service.list(RecordFilter(mission_id=demo["missions"][0].id))
        assert page.H == first["H"] + 1
    finally:
        runtime.close()


def test_acceptance_wrapper_starts_real_application(tmp_path):
    """Separate process keeps fixture injection away from other test factories."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    from tests.operator.fixtures import HARNESS

    backend = Path(__file__).resolve().parents[2]
    script = """
from fastapi.testclient import TestClient
from backend_fixture import app, seed, root, main
from functools import partial
# Native host test mirrors the two private container mounts through constructors.
main.POIManager = partial(main.POIManager, pois_file=root / 'pois.json')
main.RouteManager = partial(main.RouteManager, routes_dir=root / 'routes')
original_sources = main.SourceStore
main.SourceStore = lambda missions, routes: original_sources(missions, root / 'routes')
with TestClient(app) as client:
    health = client.get('/api/v2/operator/health')
    assert health.status_code == 200, health.text
    assert health.json()['source_mode'] == 'simulation'
    assert health.json()['simulation_run_id'] == seed['run_id']
    records = client.get('/api/v2/operator/records', params={'mission_id': seed['mission_ids'][0]})
    assert records.status_code == 200, records.text
    assert len(records.json()['items']) == 3
    assert client.get('/health').status_code == 200
    assert client.post('/api/v2/operator/clock').status_code == 404
    assert client.post('/api/v2/operator/reset').status_code == 404
assert not hasattr(app.state, 'operator_binding')
print('synthetic real-app startup and shutdown passed')
"""
    env = dict(
        os.environ,
        PYTHONPATH=os.pathsep.join([str(HARNESS), str(backend)]),
        OPERATOR_ACCEPTANCE_FIXTURE="synthetic-local-only",
        STARLINK_MODE="simulation",
        SIMULATION_MODE="true",
        OPERATOR_ENABLED="true",
        OPERATOR_ACCEPTANCE_ROOT=str(tmp_path / "data"),
        STARLINK_DISABLE_BACKGROUND_TASKS="1",
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=40,
    )
    assert result.returncode == 0, result.stdout + result.stderr
