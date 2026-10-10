"""Pure one-leg document payload; never classifies or renders availability."""

import json

from .briefing_clocks import ensure_utc
from .customer_display import display_row
from .customer_projection import BriefingLeg, project_briefing_leg
from .customer_view import CustomerLegView, project_customer_leg, restriction_labels
from .map_inputs import build_map_input
from .snapshot import ExportSnapshot


def stamp(value):
    return ensure_utc(value).isoformat().replace("+00:00", "Z")


def build_customer_document(
    snapshot: ExportSnapshot, view: CustomerLegView, projection: BriefingLeg
) -> dict:
    if (
        len(snapshot.legs) != 1
        or snapshot.legs[0].leg_id != projection.leg_id
        or view.leg_id != projection.leg_id
    ):
        raise ValueError("Checkpoint requires one matching leg")
    return _leg_payload(snapshot, snapshot.legs[0], view, projection)


def build_customer_mission_document(snapshot: ExportSnapshot) -> dict:
    if not snapshot.legs or len({leg.leg_id for leg in snapshot.legs}) != len(
        snapshot.legs
    ):
        raise ValueError("Mission requires nonempty unique legs")
    legs = []
    for number, captured in enumerate(snapshot.legs, 1 + snapshot.leg_number_offset):
        projection = project_briefing_leg(captured)
        view = project_customer_leg(
            captured,
            projection,
            leg_number=captured.display_number or number,
            leg_count=snapshot.leg_count or len(snapshot.legs),
        )
        legs.append(_leg_payload(snapshot, captured, view, projection))
    return {
        "schemaVersion": 2,
        "missionId": snapshot.mission_id,
        "snapshotFingerprint": snapshot.fingerprint,
        "legs": legs,
    }


def _leg_payload(snapshot, captured, view, projection):
    if (
        not projection.utc_bounds
        or captured.utc_bounds != projection.utc_bounds
        or captured.leg_id != projection.leg_id
        or view.leg_id != projection.leg_id
        or view.intervals != projection.intervals
    ):
        raise ValueError("Checkpoint bounds/projection mismatch")
    start, end = map(ensure_utc, projection.utc_bounds)
    cursor = start
    for interval in projection.intervals:
        a, b = map(ensure_utc, (interval.start_time, interval.end_time))
        if a != cursor or b <= a or b > end or len(interval.decisions) != 3:
            raise ValueError("Unordered, gapped or invalid interval partition")
        cursor = b
    if cursor != end:
        raise ValueError("Incomplete interval partition")
    ids = {i.id for i in projection.intervals}
    if any(
        not set(r.interval_ids) <= ids or not start <= r.start_time < r.end_time <= end
        for r in view.rows
    ):
        raise ValueError("Customer rows do not match partition")
    if len({r.id for r in view.rows}) != len(view.rows) or any(
        a.end_time > b.start_time for a, b in zip(view.rows, view.rows[1:])
    ):
        raise ValueError("Unordered or duplicate customer rows")
    map_input, map_reasons = build_map_input(captured, projection)
    if map_input:
        map_input = json.loads(json.dumps(map_input))
        leg = json.loads(captured.leg_json)
        map_input["endpointLabels"] = {
            "departure": leg.get("departure_airport") or "Departure",
            "arrival": leg.get("arrival_airport") or "Arrival",
        }
        # Customer overview shows the route and airports; exact events stay in evidence.
        map_input["markers"] = []
    payload = {
        "schemaVersion": 1,
        "snapshotFingerprint": snapshot.fingerprint,
        "legId": projection.leg_id,
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
            for i in projection.intervals
        ],
        "rows": [
            {
                "id": r.id,
                "startUtc": stamp(r.start_time),
                "endUtc": stamp(r.end_time),
                "et": r.clock.start + "–" + r.clock.end,
                "impact": r.impact,
                "remaining": r.remaining,
                "posture": r.posture,
            }
            for r in view.rows
        ],
        "mapInput": map_input,
        "mapInputDiagnostics": list(map_reasons),
    }
    for row in payload["rows"]:
        row["displayCells"] = list(display_row(row))
    return payload
