"""Mission journals survive replay replacement without reviving old reports."""

from uuid import uuid4

from app.operator.models import CreateRecord, RecordFilter
from app.operator.runtime import OperatorRuntimeBinding
from tests.operator.service_helpers import submit, update


def test_mission_journal_survives_replays_and_restart(
    service, clock, record_data, monkeypatch
):
    monkeypatch.setenv("OPERATOR_ENABLED", "true")
    monkeypatch.setenv("OPERATOR_ROOT", str(service.store.settings.root))
    source = ["simulation", "replay-a"]
    binding = OperatorRuntimeBinding(
        clock=clock, context=lambda: tuple(source), mission_journals=True
    )
    with binding.access() as runtime:
        assert runtime.health().error_code == "store_initialization_required"
        runtime.provision(
            expected_mode="simulation", expected_run=runtime.health().simulation_run_id
        )
        first = submit(
            runtime.service, CreateRecord.model_validate(record_data)
        ).saved_records[0]
        identity = runtime.health().store_id
        epoch = runtime.health().api_epoch
        assert first.provenance.replay_run_id == "replay-a"
    source[1] = "replay-b"
    with binding.access() as runtime:
        assert runtime.health().store_id == identity
        assert runtime.health().api_epoch == epoch
        assert runtime.health().replay_run_id == "replay-b"
        assert runtime.service.get(first.record_id) == first
        corrected = submit(
            runtime.service, update(runtime.service, first)
        ).saved_records[0]
        assert corrected.provenance.replay_run_id == "replay-a"
        from app.operator.replay_context import current_records

        assert current_records([corrected], runtime.health()) == []
        assert (
            runtime.service.list(RecordFilter(mission_id="other-mission")).items == []
        )
    binding.close()
    binding = OperatorRuntimeBinding(
        clock=clock, context=lambda: ("simulation", None), mission_journals=True
    )
    with binding.access() as runtime:
        assert runtime.health().ready
        assert runtime.service.get(first.record_id).version == 2
    binding.close()
    monkeypatch.setenv("OPERATOR_EVALUATION_SESSION", "second-evaluation")
    binding = OperatorRuntimeBinding(
        clock=clock, context=lambda: tuple(source), mission_journals=True
    )
    with binding.access() as runtime:
        assert runtime.health().error_code == "store_initialization_required"
        runtime.provision(
            expected_mode="simulation", expected_run=runtime.health().simulation_run_id
        )
        assert runtime.health().store_id != identity
        assert runtime.service.list(RecordFilter(mission_id="demo-mission")).items == []
    binding.close()


def test_current_context_uses_existing_resolver_without_requiring_ready_store(
    api, monkeypatch
):
    from types import SimpleNamespace

    from app.mission import active_context

    context = SimpleNamespace(
        parent_mission_id="demo-mission",
        parent_mission=SimpleNamespace(name="Demo mission"),
        leg=SimpleNamespace(id="leg-a", name="Leg A"),
    )
    monkeypatch.setattr(
        active_context,
        "resolve_active_mission_leg_context",
        lambda manager: SimpleNamespace(state="available", context=context),
    )
    api.app.state.route_manager = object()
    response = api.get("/api/v2/operator/context")
    assert response.status_code == 200
    assert response.json()["mission_id"] == "demo-mission"
    assert response.json()["leg_name"] == "Leg A"
    monkeypatch.setattr(
        active_context,
        "resolve_active_mission_leg_context",
        lambda manager: SimpleNamespace(state="no_active_mission", context=None),
    )
    assert api.get("/api/v2/operator/context").json()["mission_id"] is None


def test_legacy_run_journal_is_not_adopted_or_changed(
    service, clock, record_data, monkeypatch
):
    from app.operator.runtime import OperatorRuntime
    from app.operator.settings import OperatorSettings

    root = service.store.settings.root
    legacy = OperatorRuntime.start(
        OperatorSettings(
            enabled=True,
            root=root,
            source_mode="simulation",
            simulation_run_id="replay-a",
        ),
        clock=clock,
    )
    legacy.provision(expected_mode="simulation", expected_run="replay-a")
    saved = submit(
        legacy.service, CreateRecord.model_validate(record_data)
    ).saved_records[0]
    legacy.close()
    legacy_path = root / "simulation" / "replay-a" / "operations.sqlite3"
    before = legacy_path.read_bytes()
    monkeypatch.setenv("OPERATOR_ENABLED", "true")
    monkeypatch.setenv("OPERATOR_ROOT", str(root))
    binding = OperatorRuntimeBinding(
        clock=clock, context=lambda: ("simulation", "replay-a"), mission_journals=True
    )
    with binding.access() as runtime:
        assert not runtime.health().ready
        runtime.provision(expected_mode="simulation", expected_run="default")
        assert runtime.service.list(RecordFilter(mission_id="demo-mission")).items == []
        from app.operator.projections import capture_projection

        assert (
            capture_projection(
                runtime.service.store, mission_id="demo-mission", include_audit=True
            ).high_water
            == 0
        )
    binding.close()
    assert legacy_path.read_bytes() == before
    legacy = OperatorRuntime.start(
        OperatorSettings(
            enabled=True,
            root=root,
            source_mode="simulation",
            simulation_run_id="replay-a",
        ),
        clock=clock,
    )
    assert legacy.service.get(saved.record_id) == saved
    legacy.close()


def test_replay_guard_rejects_new_old_run_writes_but_returns_existing_receipts(
    service, clock, record_data, monkeypatch
):
    import pytest

    from app.operator.errors import OperatorError

    monkeypatch.setenv("OPERATOR_ENABLED", "true")
    monkeypatch.setenv("OPERATOR_ROOT", str(service.store.settings.root))
    source = ["simulation", "replay-a"]
    binding = OperatorRuntimeBinding(
        clock=clock, context=lambda: tuple(source), mission_journals=True
    )
    command, key = CreateRecord.model_validate(record_data), str(uuid4())
    with binding.access() as runtime:
        runtime.provision(expected_mode="simulation", expected_run="default")
        epoch = str(runtime.health().api_epoch)
        receipt = runtime.service.execute_result(
            command, key=key, epoch=epoch, expected_replay="replay-a"
        )
    source[1] = "replay-b"
    with binding.access() as runtime:
        assert (
            runtime.service.execute_result(
                command, key=key, epoch=epoch, expected_replay="replay-a"
            ).receipt
            == receipt.receipt
        )
        with pytest.raises(OperatorError, match="store_context_changed"):
            runtime.service.execute_result(
                command, key=str(uuid4()), epoch=epoch, expected_replay="replay-a"
            )
    binding.close()


def test_replay_retains_requirements_but_not_connections_checks_or_old_alert_generations(
    service, clock, record_data, monkeypatch
):
    from app.operator.event_feed import build_snapshot
    from app.operator.event_sources import EventSourceAdapter
    from app.operator.replay_context import current_records
    from tests.operator.test_call_api import call_data
    from tests.operator.test_conference_actions import participation
    from tests.operator.test_conference_api import conference_data
    from tests.operator.test_transport_contract import decision, row

    monkeypatch.setenv("OPERATOR_ENABLED", "true")
    monkeypatch.setenv("OPERATOR_ROOT", str(service.store.settings.root))
    source = ["simulation", "run-a"]
    binding = OperatorRuntimeBinding(
        clock=clock, context=lambda: tuple(source), mission_journals=True
    )
    with binding.access() as runtime:
        runtime.provision(expected_mode="simulation", expected_run="default")
        bridge = submit(
            runtime.service,
            CreateRecord.model_validate(
                conference_data(
                    record_data, status="established", verified_at=clock.now()
                )
            ),
        ).saved_records[0]
        submit(
            runtime.service,
            CreateRecord.model_validate(
                participation(record_data, str(bridge.record_id), state="connected")
            ),
        )
        submit(
            runtime.service,
            CreateRecord.model_validate(
                decision(record_data, row(checked={"result": "satisfactory"}))
            ),
        )
        submit(
            runtime.service,
            CreateRecord.model_validate(call_data(record_data, status="completed")),
        )
        requirement = submit(
            runtime.service, CreateRecord.model_validate(call_data(record_data))
        ).saved_records[0]
        before = build_snapshot(
            runtime, "demo-mission", EventSourceAdapter(runtime.service)
        )
        assert len(before.transport_review.activities) > 0
    source[1] = "run-b"
    with binding.access() as runtime:
        all_records = runtime.service.list(
            RecordFilter(mission_id="demo-mission")
        ).items
        assert len(all_records) == 5
        assert current_records(all_records, runtime.health()) == [requirement]
        after = build_snapshot(
            runtime, "demo-mission", EventSourceAdapter(runtime.service)
        )
        assert not after.transport_review.assessments
        assert not any(
            a.kind == "participation" for a in after.transport_review.activities
        )
        assert all(not event.protected_participation_ids for event in after.events)
        before_ids = {e.notification.generation for e in before.events if e.active}
        after_ids = {e.notification.generation for e in after.events if e.active}
        assert after_ids and not before_ids & after_ids
        from app.operator.projections import capture_projection

        projection = capture_projection(
            runtime.service.store, mission_id="demo-mission", include_audit=True
        )
        import json

        from app.mission.package.operations_archive import journal_files

        archive = journal_files(projection)
        assert (
            b"Historical replay report; not current readiness"
            in archive["operations/handover.txt"]
        )
        assert (
            json.loads(archive["operations/journal.json"])["replay_run_id"] == "run-b"
        )
        assert len(json.loads(projection.files["operations/current.json"])) == 5
        assert len(projection.files["operations/audit.jsonl"].splitlines()) == 5
    binding.close()


def test_explicit_start_of_carried_call_reports_new_run_without_refreshing_old_started_calls(
    service, clock, record_data, monkeypatch
):
    from app.operator.replay_context import current_records
    from tests.operator.test_call_api import call_data

    monkeypatch.setenv("OPERATOR_ENABLED", "true")
    monkeypatch.setenv("OPERATOR_ROOT", str(service.store.settings.root))
    source = ["simulation", "run-a"]
    binding = OperatorRuntimeBinding(
        clock=clock, context=lambda: tuple(source), mission_journals=True
    )
    with binding.access() as runtime:
        runtime.provision(expected_mode="simulation", expected_run="default")
        requirement = submit(
            runtime.service, CreateRecord.model_validate(call_data(record_data))
        ).saved_records[0]
    source[1] = "run-b"
    with binding.access() as runtime:
        started = submit(
            runtime.service,
            update(
                runtime.service,
                requirement,
                time=requirement.time.model_copy(
                    update={
                        "occurred_at": clock.now(),
                        "precision": "exact",
                        "end_state": "ongoing",
                    }
                ),
            ),
        ).saved_records[0]
        assert started.provenance.replay_run_id == "run-b"
        assert current_records([started], runtime.health()) == [started]
        assert (
            runtime.service.history(started.record_id)
            .items[-1]
            .provenance.replay_run_id
            == "run-b"
        )
    source[1] = "run-c"
    with binding.access() as runtime:
        assert current_records([started], runtime.health()) == []
        corrected = submit(
            runtime.service, update(runtime.service, started)
        ).saved_records[0]
        assert corrected.provenance.replay_run_id == "run-b"
        assert current_records([corrected], runtime.health()) == []
    binding.close()


def test_cancelled_or_failed_replay_is_not_current_operational_evidence(monkeypatch):
    from types import SimpleNamespace

    import main

    monkeypatch.setattr(
        main, "_current_runtime_config", lambda: SimpleNamespace(mode="simulation")
    )
    status = SimpleNamespace(state="running", run=SimpleNamespace(run_id="run-a"))
    monkeypatch.setattr(
        main.app.state,
        "simulation_run_service",
        SimpleNamespace(status=lambda: status),
        raising=False,
    )
    assert main._operator_context() == ("simulation", "run-a")
    status.state = "completed"
    assert main._operator_context() == ("simulation", "run-a")
    for state in ("cancelled", "failed", "idle"):
        status.state = state
        assert main._operator_context() == ("simulation", None)
