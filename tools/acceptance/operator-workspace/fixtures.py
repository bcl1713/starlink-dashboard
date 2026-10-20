"""Deterministic workspace prerequisites, never completed learner actions.

The caller owns the app/data root and submits planned calls through the existing
Operator service. There are deliberately no receipts, actual join/leave events,
flight phases, predictor outputs or expected ETAs in this fixture.
"""

from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5


def build_workspace_fixture(seed: str) -> dict:
    """Build normal or five-customer busy inputs with reproducible identities."""
    if seed not in {"normal", "busy"}:
        raise ValueError("Workspace seed must be normal or busy")
    namespace = f"synthetic-operator-workspace-v1/{seed}"
    mission_id = str(uuid5(NAMESPACE_URL, namespace + "/mission"))
    leg_ids = [str(uuid5(NAMESPACE_URL, namespace + f"/leg/{i}")) for i in (1, 2)]
    start = datetime(2026, 10, 17, 16, tzinfo=timezone.utc)
    calls = []
    for index in range(5 if seed == "busy" else 1):
        planned = start + timedelta(minutes=20 + index * 3)
        calls.append(
            {
                "schema_version": 1,
                "record_type": "call",
                "mission_id": mission_id,
                "leg_id": leg_ids[0],
                "scope": "leg",
                "time": {
                    "occurred_at": None,
                    "ended_at": None,
                    "precision": "unknown",
                    "end_state": "unknown",
                    "planned_start_at": planned.isoformat(),
                    "planned_end_at": (planned + timedelta(minutes=15)).isoformat(),
                },
                "payload": {
                    "schema_version": 1,
                    "entry_type": "call",
                    "title": f"Synthetic customer {index + 1} briefing",
                    "party": f"Synthetic customer {index + 1}",
                    "note": "Fictional planned prerequisite; no connection reported.",
                    "previous_leg_id": None,
                    "next_leg_id": None,
                    "status": "scheduled",
                    "conference_id": None,
                    "coordinator": "Synthetic coordinator",
                    "communications_kind": "voice",
                    "prep_lead_minutes": 10,
                },
            }
        )
    return {
        "synthetic": True,
        "seed": seed,
        "namespace": namespace,
        "started_at": start.isoformat(),
        "mission": {
            "id": mission_id,
            "name": f"Synthetic workspace {seed}",
            "legs": [
                {
                    "id": leg_id,
                    "name": f"Synthetic leg {index + 1}",
                    "route_id": "synthetic-route",
                    "transports": {"initial_x_satellite_id": "X-1"},
                }
                for index, leg_id in enumerate(leg_ids)
            ],
        },
        "planned_commands": calls,
        "raw_samples": [
            {"offset_seconds": offset, "latitude": 0, "longitude": longitude,
             "speed_knots": 600}
            for offset, longitude in [(0, -10), (600, 0), (2400, 10)]
        ],
    }
