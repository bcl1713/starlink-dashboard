"""Source approval required before generating proposals, independent of plan approval."""

import math

from .errors import PlanningFailure
from .store import selection_errors


def validate_generation(leg, *, availability=None, start=None, end=None):
    draft = leg.draft
    errors = selection_errors(
        draft,
        availability=availability,
        start=start or leg.departure_time,
        end=end or leg.arrival_time,
    )
    if errors:
        raise PlanningFailure(422, errors[0].code, errors[0].message)
    rows = draft.ar_corrections or leg.ar_rows
    active = [row for row in rows if row.match_status != "excluded"]
    if (
        not leg.route
        or leg.ar_section_status == "unrecognized"
        or any(
            not row.confirmed
            or row.match_status != "matched"
            or not row.confirmed_units
            or row.source_altitude is None
            or not math.isfinite(row.source_altitude)
            or row.source_altitude <= 0
            for row in active
        )
        or any(
            not (row.exclusion_note or "").strip()
            for row in rows
            if row.match_status == "excluded"
        )
        or (not active and not draft.no_ars_confirmed)
    ):
        raise PlanningFailure(
            422,
            "source_review_required",
            "Review AR times, occurrences and altitudes, or explicitly confirm no ARs, before generating plans",
            action="review_source",
        )
