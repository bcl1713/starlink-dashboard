"""Issue correction validation and automatic audit reasons within the transaction."""

from datetime import timedelta

from .errors import OperatorError
from .queries import select_records
from .time_models import utc_timestamp


def validate_issue_update(connection, current, command, clock):
    if command.record_type != "issue":
        return
    payload = command.payload
    if (
        payload.corrected_update_at is not None
        and payload.corrected_update_at
        > utc_timestamp(clock.now()) + timedelta(seconds=60)
    ):
        raise OperatorError(
            "validation_error",
            fields={"payload.corrected_update_at": "Actual time is in the future"},
        )
    if payload.corrects_version is None:
        return
    if current is None:
        raise OperatorError(
            "validation_error",
            fields={
                "payload.corrects_version": "Correction requires an existing issue update"
            },
        )
    targets = select_records(
        connection,
        "SELECT * FROM revisions WHERE record_id=? AND version=?",
        (str(current.record_id), payload.corrects_version),
    )
    if (
        not targets
        or targets[0].deleted
        or targets[0].operation not in ("create", "update")
        or not targets[0].payload.update_text.strip()
    ):
        raise OperatorError(
            "validation_error",
            fields={
                "payload.corrects_version": "Target must be a retained issue update"
            },
        )
    allowed = {"update_text", "corrects_version", "corrected_update_at"}
    before = current.payload.model_dump(exclude=allowed)
    after = payload.model_dump(exclude=allowed)
    if (
        command.time != current.time
        or before != after
        or any(
            getattr(command, name) != getattr(current, name)
            for name in ("mission_id", "leg_id", "scope")
        )
    ):
        raise OperatorError(
            "validation_error",
            fields={
                "payload.corrects_version": "Historical correction must preserve current issue state"
            },
        )


def issue_audit_reason(current, command):
    if command.record_type != "issue":
        return None
    payload = command.payload
    if payload.corrects_version is not None:
        return "Issue update corrected"
    if current is None:
        return "Issue opened"
    actions = []
    if current.payload.status != payload.status:
        actions.append(
            {
                "open": "Issue opened",
                "monitoring": "Issue monitoring",
                "resolved": "Issue resolved",
                "reopened": "Issue reopened",
            }[payload.status]
        )
    if current.payload.mitigation != payload.mitigation:
        actions.append("Issue mitigation updated")
    if current.payload.follow_up_at != payload.follow_up_at:
        actions.append("Issue follow-up updated")
    if payload.update_text.strip():
        actions.append("Issue update recorded")
    return "; ".join(actions) or "Issue details corrected"
