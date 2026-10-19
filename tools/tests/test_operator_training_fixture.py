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
    scenario.apply_checkpoint(root, "leg-one")
    second = scenario.seed_prerequisites(root)
    assert first["store_id"] == second["store_id"]
    assert first["api_epoch"] == second["api_epoch"]
    assert first["record_ids"] == second["record_ids"]
    assert first["H"] == second["H"]
    assert first["learner_actions_seeded"] is False
    assert len(first["leg_ids"]) == 2
    assert len(first["record_ids"]) == 8
    import json

    mission = json.loads(
        (root / "missions" / first["mission_id"] / "mission.json").read_text()
    )
    assert mission["metadata"]["operator_training_fixture"] == {
        "version": 1,
        "namespace": first["namespace"],
        "prerequisite_record_ids": first["record_ids"],
    }


def test_real_records_acknowledgments_and_receipts_share_fixture_namespace_across_segments(
    tmp_path, monkeypatch
):
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from uuid import uuid4

    from app.api.operator import router
    from app.mission import storage
    from app.operator.runtime import OperatorRuntimeBinding
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

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


def test_existing_scenario_clock_follows_persisted_forward_checkpoints_and_restart(
    tmp_path,
):
    root = tmp_path / "clock"
    scenario.mark_root(root)
    clock = scenario.training_clock(root)
    initial = clock.now()
    scenario.apply_checkpoint(root, "leg-one")
    assert (clock.now() - initial).total_seconds() == 15 * 60
    assert clock.monotonic() == 15 * 60
    assert scenario.training_clock(root).now() == clock.now()
    with pytest.raises(ValueError, match="backwards"):
        scenario.apply_checkpoint(root, "preflight")


def test_existing_raw_input_helper_can_leave_learner_actions_routes_and_phase_untouched(
    tmp_path, monkeypatch
):
    from datetime import datetime, timezone
    from types import SimpleNamespace

    # Load this shared helper independently of test collection order. The
    # training CLI's shadowed scenario is exercised by its separate CLI test.
    monkeypatch.syspath_prepend(str(ROOT / "tools/acceptance/operator-journal"))
    monkeypatch.setitem(sys.modules, "scenario", scenario._existing_clock_module())
    import model_inputs_fixture

    monkeypatch.setattr(
        model_inputs_fixture,
        "seed_events",
        lambda *_: (_ for _ in ()).throw(
            AssertionError("Learner actions must not be seeded")
        ),
    )
    monkeypatch.setattr(
        model_inputs_fixture.ModelInputsFixture, "update", lambda *_: None
    )
    (tmp_path / "operator").mkdir()
    helper = model_inputs_fixture.ModelInputsFixture(
        SimpleNamespace(),
        SimpleNamespace(service=None),
        tmp_path,
        SimpleNamespace(now=lambda: datetime(2026, 10, 17, 16, tzinfo=timezone.utc)),
        seed=False,
        manage_route=False,
        restore_phase=False,
    )
    assert helper.ids == {}
    assert not helper.manage_route
    assert not helper.restore_phase


def test_training_entrypoint_refuses_live_and_unmarked_roots_before_startup(
    tmp_path, monkeypatch
):
    import runpy

    monkeypatch.setenv("OPERATOR_TRAINING_FIXTURE", "explicit-private-training-v1")
    monkeypatch.setenv("OPERATOR_TRAINING_ROOT", str(tmp_path / "unmarked"))
    monkeypatch.setenv("STARLINK_MODE", "live")
    entrypoint = ROOT / "tools/training/operator-mission/backend.py"
    with pytest.raises(RuntimeError, match="simulation"):
        runpy.run_path(str(entrypoint))
    monkeypatch.setenv("STARLINK_MODE", "simulation")
    with pytest.raises(ValueError, match="marked"):
        runpy.run_path(str(entrypoint))
    assert not (tmp_path / "unmarked").exists()


def test_training_compose_has_only_private_volumes_and_readonly_source_mounts():
    import yaml

    compose = yaml.safe_load(
        (ROOT / "docker-compose.operator-training.yml").read_text()
    )
    assert all(not volume.get("external") for volume in compose["volumes"].values())
    assert compose["networks"]["default"]["internal"] is True
    backend = compose["services"]["starlink-location"]
    assert backend["environment"]["STARLINK_MODE"] == "simulation"
    assert all(
        mount["read_only"] for mount in backend["volumes"] if mount["type"] == "bind"
    )
    assert {
        mount["source"] for mount in backend["volumes"] if mount["type"] == "volume"
    } == {"training-data", "training-routes"}
    assert all(
        str(port).startswith("127.0.0.1:")
        for port in compose["services"]["mission-planner"]["ports"]
    )


def test_training_routes_use_normal_parser_and_have_two_distinct_replay_windows(
    tmp_path,
):
    from app.services.kml_parser import parse_kml_file

    root = tmp_path / "routes"
    scenario.mark_root(root)
    scenario.seed_prerequisites(root)
    files = sorted((root / "route-data/routes").glob("*.kml"))
    assert len(files) == 2
    routes = [parse_kml_file(path) for path in files]
    assert all(route and route.timing_profile.has_timing_data for route in routes)
    assert (
        routes[1].timing_profile.departure_time > routes[0].timing_profile.arrival_time
    )
    assert routes[0].points[0].longitude == -10
    assert routes[1].points[0].longitude == 10
    from app.mission import storage

    previous = storage.MISSIONS_DIR
    try:
        storage.MISSIONS_DIR = root / "missions"
        mission = storage.load_mission_v2("4063022a-14a6-5c70-94b0-1d790a01311b")
        assert [leg.route_id for leg in mission.legs] == [
            "operator-training-leg-1",
            "operator-training-leg-2",
        ]
        assert mission.legs[0].name == "First flight · Meridian to Harbor"
    finally:
        storage.MISSIONS_DIR = previous


def test_launcher_refuses_shared_or_external_volume_configuration(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "operator_training_launcher",
        ROOT / "tools/training/operator-mission/launcher.py",
    )
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    with pytest.raises(ValueError, match="private"):
        launcher.validate_project("dev", "12345678-1234-1234-1234-123456789abc")
    with pytest.raises(ValueError, match="volume"):
        launcher.validate_compose(
            {"services": {}, "volumes": {"bad": {"external": True}}},
            tmp_path,
            "starlink-operator-training-123456781234",
        )


def test_corrupt_launcher_ownership_is_preserved_before_any_command(tmp_path):
    import os

    spec = importlib.util.spec_from_file_location(
        "operator_training_launcher_guard",
        ROOT / "tools/training/operator-mission/launcher.py",
    )
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    root = tmp_path / "corrupt-owner"
    marker = scenario.mark_root(root)
    value = {
        "project": "starlink-operator-training-"
        + marker["root_id"].replace("-", "")[:12],
        "trainingRootId": marker["root_id"],
        "candidateSha": "broken",
        "port": 12345,
        "disposable": False,
        "dockerHost": os.getenv("DOCKER_HOST"),
        "dockerContext": os.getenv("DOCKER_CONTEXT"),
        "commands": [],
    }
    import json

    raw = json.dumps(value)
    (root / "ownership.json").write_text(raw)
    with pytest.raises(ValueError, match="candidate"):
        launcher.open_owner(root)
    assert (root / "ownership.json").read_text() == raw


def test_raw_helper_uses_current_checkpoint_time_even_if_restart_precedes_application(
    tmp_path, monkeypatch
):
    import json
    from datetime import datetime, timezone
    from types import SimpleNamespace

    # Load this shared helper independently of test collection order. The
    # training CLI's shadowed scenario is exercised by its separate CLI test.
    monkeypatch.syspath_prepend(str(ROOT / "tools/acceptance/operator-journal"))
    monkeypatch.setitem(sys.modules, "scenario", scenario._existing_clock_module())
    import model_inputs_fixture

    directory = tmp_path / "operator"
    directory.mkdir()
    (directory / "synthetic-model-inputs.json").write_text(
        json.dumps({"now": "2026-10-17T16:00:00Z"})
    )
    monkeypatch.setattr(
        model_inputs_fixture.ModelInputsFixture, "update", lambda *_: None
    )
    helper = model_inputs_fixture.ModelInputsFixture(
        SimpleNamespace(),
        SimpleNamespace(service=None),
        tmp_path,
        SimpleNamespace(now=lambda: datetime(2026, 10, 17, 17, 5, tzinfo=timezone.utc)),
        seed=False,
        manage_route=False,
        restore_phase=False,
        initial_inputs={"now": "2026-10-17T17:05:00Z"},
    )
    assert helper.state["now"] == "2026-10-17T17:05:00Z"


def test_launcher_refuses_switching_recorded_instance_purpose(tmp_path):
    import json
    import os

    spec = importlib.util.spec_from_file_location(
        "operator_training_purpose_guard",
        ROOT / "tools/training/operator-mission/launcher.py",
    )
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    root = tmp_path / "private"
    marker = scenario.mark_root(root)
    value = {
        "project": "starlink-operator-training-"
        + marker["root_id"].replace("-", "")[:12],
        "trainingRootId": marker["root_id"],
        "candidateSha": "a" * 40,
        "port": 12345,
        "disposable": True,
        "destination": True,
        "dockerHost": os.getenv("DOCKER_HOST"),
        "dockerContext": os.getenv("DOCKER_CONTEXT"),
        "commands": [],
    }
    raw = json.dumps(value)
    (root / "ownership.json").write_text(raw)
    with pytest.raises(ValueError, match="purpose"):
        launcher.open_owner(root, destination=False)
    assert (root / "ownership.json").read_text() == raw


def test_stopping_parent_also_stops_its_owned_disposable_import_destination(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace

    spec = importlib.util.spec_from_file_location(
        "operator_training_child_cleanup",
        ROOT / "tools/training/operator-mission/launcher.py",
    )
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    child_root = tmp_path / "import-destination"
    child_root.mkdir()
    (child_root / "ownership.json").write_text("owned child")
    commands = []

    def owner(root, name):
        return SimpleNamespace(
            root=root,
            project=name,
            ownership={"disposable": True},
            compose=lambda *args, **kwargs: commands.append((name, args)),
            persist=lambda: None,
        )

    parent = owner(tmp_path, "parent")
    child = owner(child_root, "child")

    def open_child(path, **kwargs):
        assert path == child_root
        assert kwargs == {"destination": True}
        return child

    monkeypatch.setattr(launcher, "open_owner", open_child)
    monkeypatch.setattr(launcher, "validate", lambda owned: None)
    monkeypatch.setattr(launcher, "stop_relay", lambda owned: None)
    monkeypatch.setattr(
        launcher,
        "check_resources",
        lambda owned: {"container": [], "network": [], "volume": []},
    )
    launcher.stop(parent, retain=True)
    assert commands == [("child", ("down", "--volumes")), ("parent", ("down",))]


def test_reset_records_successor_ownership_before_start_and_retains_old_data(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace

    spec = importlib.util.spec_from_file_location(
        "operator_training_reset_ownership",
        ROOT / "tools/training/operator-mission/launcher.py",
    )
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    parent = SimpleNamespace(
        root=tmp_path / "private", ownership={}, persist=lambda: None
    )
    stopped = []
    monkeypatch.setattr(
        launcher, "stop", lambda owned, **kwargs: stopped.append((owned, kwargs))
    )

    def create_successor(path, **kwargs):
        assert parent.ownership["resetSuccessor"] == str(path)
        assert path.parent == parent.root.parent
        assert path.name.startswith("private-reset-")
        assert kwargs == {"create": True, "disposable": True}
        return SimpleNamespace(root=path)

    monkeypatch.setattr(launcher, "open_owner", create_successor)
    monkeypatch.setattr(
        launcher,
        "start",
        lambda owned, **kwargs: "http://127.0.0.1:12345/operator?workspace=1",
    )
    result = launcher.reset_root(parent, disposable=True, relay=True)
    assert stopped == [(parent, {"retain": True})]
    assert result["newRoot"] == parent.ownership["resetSuccessor"]
    assert result["retainedRoot"] == str(parent.root)


def test_private_maintenance_reuses_cli_with_the_fixture_clock_and_bound_namespace(
    tmp_path, monkeypatch
):
    from app.operator import __main__ as cli

    spec = importlib.util.spec_from_file_location(
        "operator_training_maintenance",
        ROOT / "tools/training/operator-mission/maintenance.py",
    )
    maintenance = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(maintenance)
    root = tmp_path / "private"
    marker = scenario.mark_root(root)
    scenario.apply_checkpoint(root, "leg-one")
    monkeypatch.setenv("OPERATOR_TRAINING_FIXTURE", "explicit-private-training-v1")
    original_clock = cli.SystemClock

    def check(args):
        assert args == [
            "backup",
            "--root",
            str(root / "operator"),
            "--mode",
            "simulation",
            "--run",
            marker["namespace"],
        ]
        assert cli.SystemClock().now().isoformat().startswith("2026-10-17T16:15")
        return 0

    monkeypatch.setattr(cli, "main", check)
    assert maintenance.run(root, "backup") == 0
    assert cli.SystemClock is original_clock
    with pytest.raises(ValueError, match="manifest"):
        maintenance.run(root, "restore", tmp_path / "operational-manifest.json")
    monkeypatch.delenv("OPERATOR_TRAINING_FIXTURE")
    with pytest.raises(ValueError, match="[Ee]xplicit"):
        maintenance.run(root, "backup")


def test_lifecycle_proof_refuses_existing_or_unowned_roots(tmp_path):
    from uuid import uuid4

    spec = importlib.util.spec_from_file_location(
        "operator_training_lifecycle_guard",
        ROOT / "tools/training/operator-mission/prove_lifecycle.py",
    )
    proof = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(proof)
    with pytest.raises(ValueError, match="task-owned"):
        proof.validate_root(tmp_path)
    root = Path("/tmp") / ("issue-376-training-lifecycle-test-" + uuid4().hex)
    assert proof.validate_root(root) == root
    root.mkdir()
    owned = root / "preserve.txt"
    try:
        owned.write_text("existing learner data")
        with pytest.raises(ValueError, match="existing"):
            proof.validate_root(root)
        assert owned.read_text() == "existing learner data"
    finally:
        owned.unlink()
        root.rmdir()


def test_lifecycle_reads_cli_json_after_compose_progress():
    from types import SimpleNamespace

    spec = importlib.util.spec_from_file_location(
        "operator_training_cli_output",
        ROOT / "tools/training/operator-mission/prove_lifecycle.py",
    )
    proof = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(proof)
    owned = SimpleNamespace(
        compose=lambda *args, **kwargs: ' Container private-maintenance Created\n{"ready": true}\n'
    )
    assert proof.maintenance(
        owned, "restore", manifest="/app/data/operator/private.json", offline=True
    ) == {"ready": True}


def test_archive_inputs_use_existing_detector_without_seeding_learner_records(
    tmp_path, monkeypatch
):
    import json

    from app.mission import storage

    root = tmp_path / "archive-training"
    scenario.mark_root(root)
    before = scenario.seed_prerequisites(root)
    monkeypatch.setenv("OPERATOR_TRAINING_FIXTURE", "explicit-private-training-v1")
    # Executing the CLI puts its own scenario.py first on sys.path.
    monkeypatch.setitem(sys.modules, "scenario", scenario)
    spec = importlib.util.spec_from_file_location(
        "training_archive_inputs_test",
        ROOT / "tools/training/operator-mission/archive_inputs.py",
    )
    inputs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(inputs)
    monkeypatch.setattr(storage, "MISSIONS_DIR", root / "missions")
    result = inputs.run(root)
    assert result["synthetic"] and result["sealedLegs"] == 2
    assert "not replay measurements" in result["relation_to_replay"]
    assert scenario.seed_prerequisites(root)["H"] == before["H"]
    assert inputs.run(root) == result
    mission = json.loads(
        (root / "missions" / before["mission_id"] / "mission.json").read_text()
    )
    assert mission["metadata"]["operator_training_archive_inputs"]["synthetic"] is True


def test_archive_inputs_refuse_unmarked_or_nonprivate_roots(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "training_archive_guard_test",
        ROOT / "tools/training/operator-mission/archive_inputs.py",
    )
    inputs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(inputs)
    monkeypatch.delenv("OPERATOR_TRAINING_FIXTURE", raising=False)
    with pytest.raises(ValueError, match="Explicit private"):
        inputs.run(tmp_path)
    monkeypatch.setenv("OPERATOR_TRAINING_FIXTURE", "explicit-private-training-v1")
    with pytest.raises(ValueError, match="marked"):
        inputs.run(tmp_path)
