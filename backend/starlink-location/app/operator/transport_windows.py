"""Communications intervals from existing records; missing evidence stays unknown."""

from datetime import timedelta

from .transport_review_models import CommunicationWindow


def overlap(start, end, other_start, other_end):
    """Half-open intervals; equal endpoints describe an instant, null is unknown."""
    if start is not None and start == end:
        if other_start is not None and other_start == other_end:
            return start == other_start
        if other_start is not None and start < other_start:
            return False
        if other_end is not None and start >= other_end:
            return False
        return True if other_start is not None and other_end is not None else None
    if other_start is not None and other_start == other_end:
        return overlap(other_start, other_end, start, end)
    if start is not None and other_end is not None and start >= other_end:
        return False
    if other_start is not None and end is not None and end <= other_start:
        return False
    return (
        None if any(v is None for v in (start, end, other_start, other_end)) else True
    )


def communication_windows(records, *, as_of, include_history=False):
    result = []
    for record in records:
        if record.deleted:
            continue
        p, t = record.payload, record.time
        common = {
            "record_id": str(record.record_id),
            "version": record.version,
            "leg_id": record.leg_id,
            "title": p.title,
        }
        historical = (
            include_history
            and p.entry_type == "call"
            and t.occurred_at is not None
            and t.ended_at is not None
        )
        if p.entry_type == "call" and (
            p.status not in ("completed", "cancelled") or historical
        ):
            actual = t.occurred_at is not None
            start = t.occurred_at if actual else t.planned_start_at
            end = t.ended_at if actual else t.planned_end_at
            if end is not None and end <= as_of and not historical:
                continue
            result.append(
                CommunicationWindow(
                    **common,
                    kind="call",
                    call_id=str(record.record_id),
                    conference_id=str(p.conference_id) if p.conference_id else None,
                    start_at=start,
                    end_at=end,
                    basis="operator_reported" if actual else "scheduled",
                    ongoing=actual and t.end_state == "ongoing"
                )
            )
            if not actual and start and p.prep_lead_minutes:
                result.append(
                    CommunicationWindow(
                        **common,
                        kind="preparation",
                        call_id=str(record.record_id),
                        conference_id=str(p.conference_id) if p.conference_id else None,
                        start_at=start - timedelta(minutes=p.prep_lead_minutes),
                        end_at=start,
                        basis="scheduled"
                    )
                )
        elif p.entry_type == "conference" and p.status == "established":
            result.append(
                CommunicationWindow(
                    **common,
                    kind="conference",
                    conference_id=str(record.record_id),
                    start_at=t.occurred_at,
                    end_at=t.ended_at,
                    basis="operator_reported",
                    ongoing=True
                )
            )
        elif p.entry_type == "participation" and p.state == "connected":
            result.append(
                CommunicationWindow(
                    **common,
                    kind="connected",
                    call_id=str(p.call_id) if p.call_id else None,
                    conference_id=str(p.conference_id) if p.conference_id else None,
                    start_at=t.occurred_at,
                    end_at=t.ended_at,
                    basis="operator_reported",
                    ongoing=True
                )
            )
    return result
