"""Acceptance inputs are deterministic, synthetic, local and privately scoped."""

import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "tools/acceptance/operator-journal"
sys.path.insert(0, str(ROOT / "backend/starlink-location"))
sys.path.insert(0, str(HARNESS))


def test_synthetic_fixture_is_deterministic_and_local(tmp_path, monkeypatch):
    assert (HARNESS / "scenario.py").is_file(), "missing deterministic fixture seam"
    scenario = importlib.import_module("scenario")
    seed = importlib.import_module("seed")
    monkeypatch.setattr(
        "socket.create_connection", lambda *a, **k: pytest.fail("network discovery")
    )
    monkeypatch.setattr(
        "socket.getaddrinfo", lambda *a, **k: pytest.fail("network discovery")
    )
    from app.operator.models import RecordFilter
    from app.operator.runtime import OperatorRuntime
    from app.operator.settings import OperatorSettings

    results = []
    for run in ("one", "two"):
        clock = scenario.ScenarioClock()
        demo = scenario.make_demo(clock)
        assert demo["synthetic"] is True
        assert all(
            m.id.startswith("synthetic-") and m.name.startswith("Synthetic")
            for m in demo["missions"]
        )
        assert len(demo["missions"][0].legs) == 2
        result = seed.seed_demo(tmp_path / run, clock=clock, mode="simulation")
        assert result == seed.seed_demo(
            tmp_path / run, clock=scenario.ScenarioClock(), mode="simulation"
        )
        assert all(
            Path(p).is_relative_to(tmp_path / run) for p in result["roots"].values()
        )
        clock.advance(60)
        runtime = OperatorRuntime.start(
            OperatorSettings(
                enabled=True,
                root=tmp_path / run / "operator",
                source_mode="simulation",
                simulation_run_id=demo["run_id"],
            ),
            clock=clock,
        )
        try:
            rows = [
                row
                for mission in demo["missions"]
                for row in runtime.service.list(
                    RecordFilter(mission_id=mission.id)
                ).items
            ]
            # UUIDs are intentionally backend-generated; compare saved semantics.
            results.append(
                sorted(
                    json.dumps(
                        {
                            "mission": row.mission_id,
                            "leg": row.leg_id,
                            "scope": row.scope,
                            "version": row.version,
                            "time": row.time.model_dump(mode="json"),
                            "payload": row.payload.model_dump(mode="json"),
                            "provenance": row.provenance.model_dump(mode="json"),
                        },
                        sort_keys=True,
                    )
                    for row in rows
                )
            )
        finally:
            runtime.close()
        for command in demo["commands"]:
            if command.record_type == "transport_report":
                assert command.payload.status.startswith("reported_")
                with pytest.raises(ValueError):
                    type(command.payload).model_validate(
                        command.payload.model_dump()
                        | {"status": "measured_routing_verified"}
                    )
    assert results[0] == results[1]
    fixture = json.loads(
        (
            ROOT / "backend/starlink-location/tests/fixtures/operator/demo.json"
        ).read_text()
    )
    assert fixture["synthetic"] and fixture["run_id"] == demo["run_id"]


def test_acceptance_wrapper_and_private_production_compose(tmp_path):
    assert (HARNESS / "backend_fixture.py").is_file(), "missing startup injection seam"
    import yaml

    compose = yaml.safe_load((HARNESS / "compose.yml").read_text())
    services = compose["services"]
    assert set(services) == {
        "starlink-location",
        "mission-planner",
        "import-destination",
    }
    assert {
        name for name, service in services.items() if not service.get("profiles")
    } == {"starlink-location", "mission-planner"}
    assert services["import-destination"]["profiles"] == ["archive"]
    assert "ports" not in services["import-destination"]
    backend = services["starlink-location"]
    assert (
        "${OPERATOR_ACCEPTANCE_ENTRYPOINT:-backend_fixture}:app" in backend["command"]
    )
    assert backend["environment"]["STARLINK_MODE"] == "simulation"
    assert backend["environment"]["OPERATOR_ENABLED"] == "true"
    assert compose["networks"]["default"]["internal"] is True
    assert backend["build"]["dockerfile"] == "backend/starlink-location/Dockerfile"
    assert "ports" not in backend and "container_name" not in backend
    assert all(
        not (value or {}).get("external") and "name" not in (value or {})
        for value in compose["volumes"].values()
    )
    assert (
        "127.0.0.1:${OPERATOR_ACCEPTANCE_PORT:?"
        in services["mission-planner"]["ports"][0]
    )
    # Exercise route registration in separate, resource-free imports. Only the
    # explicitly selected synthetic event slice has clock/source controls.
    import os
    import subprocess
    import sys

    for enabled in ("false", "true"):
        env = dict(
            os.environ,
            OPERATOR_ACCEPTANCE_FIXTURE="synthetic-local-only",
            OPERATOR_ACCEPTANCE_ROOT=str(tmp_path / enabled),
            STARLINK_MODE="simulation",
            OPERATOR_EVENTS_ACCEPTANCE=enabled,
            PYTHONPATH=str(HARNESS)
            + os.pathsep
            + str(ROOT / "backend/starlink-location"),
        )
        script = (
            "import runpy,json; value=runpy.run_path("
            + repr(str(HARNESS / "backend_fixture.py"))
            + "); print(json.dumps([getattr(route,'path','') for route in value['app'].routes]))"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        routes = json.loads(result.stdout.splitlines()[-1])
        assert ("/api/_synthetic/operator-events" in routes) == (enabled == "true")


def test_shell_scenarios_cover_preflight_leg_and_between_leg_records():
    scenario = importlib.import_module("scenario")
    demo = scenario.make_demo(scenario.ScenarioClock())
    assert len(demo["commands"]) == 6
    demo = scenario.make_demo(scenario.ScenarioClock(), include_shell=True)
    for scope in ("preflight", "leg", "between_legs"):
        mission = f"synthetic-shell-{scope.replace('_', '-')}"
        rows = [c for c in demo["commands"] if c.mission_id == mission]
        assert {c.record_type for c in rows} == {"call", "risk", "issue"}
        assert all(c.scope == scope for c in rows)
        call = next(c for c in rows if c.record_type == "call")
        assert call.time.planned_start_at.isoformat() == "2026-10-17T16:20:00+00:00"
