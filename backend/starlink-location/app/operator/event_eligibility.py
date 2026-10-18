"""Server-authoritative notification eligibility, independent of local delivery."""

from datetime import timedelta


def select_eligible(events, *, as_of):
    eligible = []
    for event in events:
        note = event.notification
        note.eligible = False
        early = (
            120
            if event.kind == "call_start"
            else 300 if event.kind == "restriction" else 0
        )
        note.threshold_at = (
            event.due_at - timedelta(seconds=early) if event.due_at else None
        )
        note.priority = (
            0
            if event.kind == "call_start"
            else (
                1
                if event.kind == "restriction" and event.protected_participation_ids
                else (
                    2
                    if event.kind == "call_prep"
                    else 3 if event.kind == "restriction" else 4
                )
            )
        )
        if (
            not event.active
            or event.state == "unknown"
            or event.freshness != "fresh"
            or not note.available
            or note.retired
            or note.acknowledged
            or not note.generation
            or note.threshold_at is None
            or as_of < note.threshold_at
        ):
            continue
        if event.kind == "pop_advisory" or (
            event.kind == "restriction"
            and event.significance in ("routine", "advisory")
        ):
            continue
        if event.kind == "issue_followup":
            if as_of > event.due_at + timedelta(minutes=15):
                continue
        elif event.end_at is not None and as_of >= event.end_at:
            continue
        elif (
            event.kind == "call_start"
            and event.end_at is None
            and as_of > event.due_at + timedelta(minutes=15)
        ):
            continue
        note.eligible = True
        eligible.append(event)
    return sorted(
        eligible, key=lambda e: (e.notification.priority, e.due_at, e.event_id)
    )
