"""Transport correction acceptance; check reports never imply verified routing."""

from datetime import timedelta
from .errors import OperatorError
from .time_models import utc_timestamp


def validate_transport_times(command, clock):
    latest = utc_timestamp(clock.now()) + timedelta(seconds=60)
    fields = {}
    for index, row in enumerate(command.payload.services):
        for name in ("requested", "applied", "checked"):
            report = getattr(row, name)
            if report and report.time.at and report.time.at > latest:
                fields[f"payload.services.{index}.{name}.time.at"] = (
                    "Actual time exceeds the acceptance clock tolerance"
                )
    if fields:
        raise OperatorError("validation_error", fields=fields)


def validate_transport_update(current, replacement):
    markers = getattr(replacement, "replacement_check_row_ids", [])
    if replacement.record_type != "transport_decision":
        if markers:
            raise OperatorError(
                "validation_error",
                fields={
                    "replacement_check_row_ids": "Only transport corrections support replacement checks"
                },
            )
        return
    rows = {r.row_id: r for r in replacement.payload.services}
    if len(set(markers)) != len(markers) or any(
        r not in rows or rows[r].checked is None for r in markers
    ):
        raise OperatorError(
            "validation_error",
            fields={
                "replacement_check_row_ids": "Replacement checks must name distinct checked rows"
            },
        )
    before = (
        {r.row_id: r for r in current.payload.services}
        if current and current.record_type == "transport_decision"
        else {}
    )
    for key, row in rows.items():
        previous = before.get(key)
        if (
            previous
            and previous.applied != row.applied
            and previous.checked
            and row.checked
            and key not in markers
        ):
            raise OperatorError(
                "validation_error",
                fields={
                    f"payload.services.{key}.checked": "Clear prior check or explicitly report a replacement check"
                },
            )


def transport_audit_reason(current, replacement):
    if replacement.record_type == "transport_decision":
        return (
            "Transport decision recorded"
            if current is None
            else "Transport decision corrected"
        )
    return None
