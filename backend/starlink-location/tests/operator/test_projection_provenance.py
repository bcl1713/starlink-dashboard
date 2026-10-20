"""Projection source times and simulation namespaces remain explicit."""

import json

from tests.operator.service_helpers import create


def lines(bundle, name="activity"):
    return [
        json.loads(row) for row in bundle.files[f"operations/{name}.jsonl"].splitlines()
    ]


def test_source_sync_is_not_inferred_retrospective(service, record_data):
    # Actual times/ETA cannot turn source-sync knowledge into a retrospective report.
    from uuid import uuid4

    from app.operator.commands import _persist_changes
    from app.operator.models import CommandReceipt, SavedRecord
    from app.operator.projections import capture_projection

    saved = SavedRecord.model_validate(
        record_data
        | {
            "record_id": str(uuid4()),
            "command_id": str(uuid4()),
            "journal_seq": 1,
            "version": 1,
            "previous_version": None,
            "operation": "create",
            "deleted": False,
            "recorded_at": "2026-10-17T16:00:00Z",
            "author": {"backend": "synthetic_source"},
            "provenance": {
                "kind": "modeled",
                "source_mode": "live",
                "mutation_origin": "source_sync",
                "observed_at": "2026-10-17T15:58:00Z",
                "predicted_at": "2026-10-17T15:59:00Z",
            },
        }
    )
    receipt = CommandReceipt(
        command_id=saved.command_id,
        response_status=201,
        saved_records=[saved],
        canonical_response={
            "schema_version": 1,
            "command_id": str(saved.command_id),
            "saved_records": [saved.model_dump(mode="json")],
        },
    )
    with service.store.connect(write=True) as connection:
        _persist_changes(
            connection, [saved], receipt, key=str(uuid4()), request_hash="synthetic"
        )
    item = lines(capture_projection(service.store, mission_id="demo-mission"))[0]
    assert item["retrospective"] is False
    assert item["provenance"]["mutation_origin"] == "source_sync"
    assert item["provenance"]["observed_at"] == "2026-10-17T15:58:00.000000Z"
    assert item["provenance"]["predicted_at"] == "2026-10-17T15:59:00.000000Z"


def test_simulation_identity_is_not_relabeled(service, tmp_path, clock, record_data):
    from app.operator.projections import capture_projection
    from app.operator.service import OperatorService
    from app.operator.settings import OperatorSettings
    from app.operator.store import OperatorStore

    store = OperatorStore.open(
        OperatorSettings(
            enabled=True,
            root=tmp_path / "sim-operator",
            source_mode="simulation",
            simulation_run_id="synthetic-run",
        ),
        initialize=True,
        clock=clock,
    )
    try:
        simulation = OperatorService(
            store, clock=clock, actor=service.actor, references=service.references
        )
        create(simulation, record_data)
        bundle = capture_projection(
            store, mission_id="demo-mission", include_audit=True
        )
        assert bundle.source_mode == bundle.manifest.source_mode == "simulation"
        assert (
            bundle.simulation_run_id
            == bundle.manifest.simulation_run_id
            == "synthetic-run"
        )
        assert lines(bundle)[0]["provenance"]["source_mode"] == "simulation"
        assert lines(bundle, "audit")[0]["provenance"]["source_mode"] == "simulation"
    finally:
        store.close()
