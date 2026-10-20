"""Conference snapshot invariants and specific automatic audit descriptions."""

from .errors import OperatorError


def validate_conference_update(current, replacement, clock):
    if replacement.record_type != "conference" or current is None:
        return
    before, after = current.payload, replacement.payload
    if (
        before.configured_transport != after.configured_transport
        and after.verified_at is not None
    ):
        raise OperatorError(
            "validation_error",
            fields={
                "payload.verified_at": "Clear verification when changing reported configuration"
            },
        )


def conference_audit_reason(current, replacement):
    payload = replacement.payload
    if replacement.record_type == "participation":
        if current is None and payload.resumes_participation_id is not None:
            return "Customer connection restored"
        previous = current.payload.state if current is not None else None
        if payload.state != previous:
            return {
                "connected": "Customer joined",
                "left": "Customer left",
                "interrupted": "Customer connection interrupted",
            }.get(payload.state)
    if replacement.record_type == "conference":
        previous = current.payload.status if current is not None else None
        if payload.status != previous:
            if previous == "interrupted" and payload.status == "established":
                return "Conference connection restored"
            return {
                "established": "Conference established",
                "interrupted": "Conference interrupted",
                "closed": "Conference closed",
                "preparing": "Conference preparation",
            }.get(payload.status)
        if current is not None and payload.verified_at != current.payload.verified_at:
            return "Conference verification updated"
    return None
