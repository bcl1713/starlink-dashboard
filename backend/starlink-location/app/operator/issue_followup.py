"""Snapshot-only issue check-in derivation; no notification delivery."""

from .time_models import utc_timestamp


def derive_issue_followup(record, *, as_of, clock_regression=False):
    due = record.payload.follow_up_at
    if record.deleted or record.payload.status == "resolved":
        state = "inactive"
    elif due is None:
        state = "unscheduled"
    elif as_of is None or clock_regression:
        state = "unknown"
    elif due > utc_timestamp(as_of):
        state = "upcoming"
    elif due == utc_timestamp(as_of):
        state = "due"
    else:
        state = "overdue"
    return {
        "record_id": str(record.record_id),
        "version": record.version,
        "follow_up_at": (
            due.isoformat(timespec="microseconds").replace("+00:00", "Z")
            if due is not None
            else None
        ),
        "state": state,
        "as_of": (
            utc_timestamp(as_of)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
            if as_of is not None
            else None
        ),
    }
