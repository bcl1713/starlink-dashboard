"""A correction is one logical update, not a second resolution."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from app.operator.projections import capture_projection
from tests.operator.service_helpers import create, submit, update


def fixture_issue(service, record_data, clock):
    actions = json.loads(
        (
            Path(__file__).parents[1] / "fixtures/operator/issue-corrections.json"
        ).read_text()
    )["actions"]
    issue = None
    for action in actions:
        clock.current = datetime.fromisoformat(action["recorded_at"])
        time = {
            "occurred_at": action["occurred_at"],
            "precision": "exact",
            "end_state": "instant",
        }
        payload = {
            "entry_type": "issue",
            "title": "Synthetic backup",
            **{
                k: v
                for k, v in action.items()
                if k not in ("recorded_at", "occurred_at")
            },
        }
        if issue is None:
            issue = create(
                service, record_data, record_type="issue", time=time, payload=payload
            )
        else:
            issue = submit(
                service, update(service, issue, time=time, payload=payload)
            ).saved_records[0]
    return issue


@pytest.mark.parametrize("audit", [False, True])
def test_correction_after_resolution_without_audit(service, record_data, clock, audit):
    issue = fixture_issue(service, record_data, clock)
    bundle = capture_projection(
        service.store, mission_id="demo-mission", include_audit=audit
    )
    rows = [
        json.loads(row)
        for row in bundle.files["operations/activity.jsonl"].splitlines()
    ]
    assert len(rows) == 4
    messages = [row for row in rows if row.get("issue_update", {}).get("is_selected")]
    assert len(messages) == 1
    message = messages[0]["issue_update"]
    assert message["text"] == "Backup intermittent"
    assert message["root_identity"]["version"] == 2
    assert message["effective_at"].startswith("2026-01-02T10:04:00")
    assert message["entered_later"] is True
    assert rows[1]["issue_update"]["superseded_by"]["version"] == 4
    assert not any(
        name.startswith("time.") or name == "payload.status"
        for name in rows[3]["changes"]
    )
    assert issue.payload.status == "resolved"
    if audit:
        assert b"Backup unavailable" in bundle.files["operations/audit.jsonl"]


def test_chained_corrections_and_pre_correction_snapshot(service, record_data, clock):
    issue = fixture_issue(service, record_data, clock)
    from app.operator.issue_activity import derive_issue_updates

    revisions = service.history(str(issue.record_id)).items
    before = derive_issue_updates(
        [r for r in revisions if r.version < 4],
        store_id=str(service.store.health().store_id),
    )
    assert before[2].is_selected
    assert before[2].text == "Backup unavailable"
    for target in (4, 2):
        clock.advance(60)
        payload = issue.payload.model_dump() | {
            "corrects_version": target,
            "corrected_update_at": None,
            "update_text": f"Synthetic correction {target}",
        }
        issue = submit(service, update(service, issue, payload=payload)).saved_records[
            0
        ]
    metadata = derive_issue_updates(
        service.history(str(issue.record_id)).items,
        store_id=str(service.store.health().store_id),
    )
    assert [
        item.root_identity.version for item in metadata.values() if item.is_selected
    ] == [2]
    assert metadata[6].effective_at is None
    assert metadata[6].entered_later is None
