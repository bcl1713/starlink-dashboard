"""Pure one-leg document payload; never classifies or renders availability."""

from .customer_view import CustomerLegView, restriction_labels
from .snapshot import ExportSnapshot
from .trial_clocks import ensure_utc
from .trial_projection import TrialLeg


def stamp(value):
    return ensure_utc(value).isoformat().replace("+00:00", "Z")


def build_customer_document(
    snapshot: ExportSnapshot, view: CustomerLegView, trial: TrialLeg
) -> dict:
    if (
        len(snapshot.legs) != 1
        or snapshot.legs[0].leg_id != trial.leg_id
        or view.leg_id != trial.leg_id
    ):
        raise ValueError("Checkpoint requires one matching leg")
    if (
        not trial.utc_bounds
        or snapshot.legs[0].utc_bounds != trial.utc_bounds
        or view.intervals != trial.intervals
    ):
        raise ValueError("Checkpoint bounds/projection mismatch")
    start, end = map(ensure_utc, trial.utc_bounds)
    cursor = start
    for interval in trial.intervals:
        a, b = map(ensure_utc, (interval.start_time, interval.end_time))
        if a != cursor or b <= a or b > end or len(interval.decisions) != 3:
            raise ValueError("Unordered, gapped or invalid interval partition")
        cursor = b
    if cursor != end:
        raise ValueError("Incomplete interval partition")
    ids = {i.id for i in trial.intervals}
    if any(
        not set(r.interval_ids) <= ids or not start <= r.start_time < r.end_time <= end
        for r in view.rows
    ):
        raise ValueError("Customer rows do not match partition")
    return {
        "schemaVersion": 1,
        "snapshotFingerprint": snapshot.fingerprint,
        "legId": trial.leg_id,
        "header": {
            "title": view.title,
            "subtitle": view.subtitle,
            "date": view.date_label,
            "timing": view.timing_label,
            "notice": view.notice,
        },
        "flight": {"startUtc": stamp(start), "endUtc": stamp(end)},
        "intervals": [
            {
                "startUtc": stamp(i.start_time),
                "endUtc": stamp(i.end_time),
                "posture": i.posture,
                "decisions": [d.value for d in i.decisions],
                "restrictionLabels": list(restriction_labels(i)),
            }
            for i in trial.intervals
        ],
        "rows": [
            {
                "id": r.id,
                "startUtc": stamp(r.start_time),
                "endUtc": stamp(r.end_time),
                "et": ("≈ " if r.clock.approximate else "")
                + r.clock.start
                + "–"
                + r.clock.end,
                "impact": r.impact,
                "remaining": r.remaining,
                "posture": r.posture,
            }
            for r in view.rows
        ],
        "mapInput": None,
    }
