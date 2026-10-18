"""Event acceptance uses actual predictors, explicit qualification and owned cleanup."""

import json

import pytest

from test_operator_journal_acceptance import implementation

FIELDS = (
    "synthetic",
    "timelineIndependent",
    "tenMinutePrep",
    "scheduleMoved",
    "cancelSuppressed",
    "protectedUnknown",
    "actualPopPrediction",
    "predictionChanged",
    "twoClients",
    "acknowledgment",
    "boundedCatchup",
    "offlineReconnect",
    "restart",
    "unavailableSources",
    "localOnly",
    "draftPreserved",
    "sameBrowserDedup",
    "hiddenTab",
)


def test_event_proof_requires_every_failure_control(tmp_path):
    runner = implementation()
    proof = {field: True for field in FIELDS}
    proof["captures"] = ["1920x1080", "390x844", "844x390"]
    del proof["sameBrowserDedup"]
    path = tmp_path / "events-proof.json"
    path.write_text(json.dumps(proof))
    with pytest.raises(ValueError, match="sameBrowserDedup"):
        runner.events_proof(tmp_path)
    proof["sameBrowserDedup"] = True
    path.write_text(json.dumps(proof))
    assert runner.events_proof(tmp_path)["actualPopPrediction"]


def test_synthetic_source_controls_publish_actual_prediction_and_invalidate(tmp_path):
    implementation()
    from events_fixture import exercise_fixture

    result = exercise_fixture(tmp_path)
    assert result["realForecast"]
    assert result["changedGeneration"]
    assert result["unguardedMutationRejected"]
    assert result["sourceFailureUnknown"]


def test_notification_probe_preserves_exports_and_recovers_ack_receipts(tmp_path):
    implementation()
    from events_probe import probe

    result = probe(tmp_path)
    assert result["oneDurableAcknowledgment"]
    assert result["operationsUnchanged"]
    assert result["backupRestore"]
    assert result["commitCrashBefore"] and result["commitCrashAfter"]


def test_real_model_proof_rejects_missing_operational_checks(tmp_path):
    runner = implementation()
    proof = {
        field: True
        for field in (
            "synthetic",
            "rawInputsOnly",
            "foregroundSoundOnce",
            "incomingProtectedActivity",
            "twoClientAcknowledgment",
            "positionUpdatesActualPop",
            "staleReason",
            "unavailableReason",
            "routeScheduleUpdated",
            "deactivationRetires",
            "restartNoResurrection",
            "offlineReconnect",
        )
    }
    proof["captures"] = ["1920x1080", "390x844", "844x390"]
    (tmp_path / "model-alerts-proof.json").write_text(json.dumps(proof))
    with pytest.raises(ValueError, match="partialIndependentWarning"):
        runner.models_proof(tmp_path)
