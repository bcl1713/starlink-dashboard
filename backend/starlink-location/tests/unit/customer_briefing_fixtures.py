"""Fixed, committed inputs shared by projection and later deck acceptance."""

import json
from datetime import datetime
from pathlib import Path

from app.mission.exporter.snapshot import LegSnapshot
from app.mission.exporter.snapshot_inputs import canonical_json

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/customer_briefing"


def utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def fixture(name):
    return json.loads((FIXTURES / f"{name.lower()}.json").read_text())


def snapshot(data):
    leg = data["mission"]["legs"][0]
    return LegSnapshot(
        leg_id=leg["id"],
        leg_json=canonical_json(leg),
        effective_route_json=canonical_json(data["route"]) if data["route"] else None,
        timeline_json=canonical_json(data["timeline"]) if data["timeline"] else None,
        source_records=tuple(canonical_json(v) for v in data["source_records"]),
        resolved_restrictions=tuple(
            canonical_json(v) for v in data["resolved_restrictions"]
        ),
        utc_bounds=(
            tuple(utc(v) for v in data["utc_bounds"]) if data["utc_bounds"] else None
        ),
        preparation_origin=data["preparation_origin"],
        warnings=tuple(data["warnings"]),
    )
