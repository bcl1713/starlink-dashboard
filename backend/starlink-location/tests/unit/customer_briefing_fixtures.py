"""Fixed, committed inputs shared by projection and later deck acceptance."""

import json
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path

from app.mission.exporter.snapshot import ExportSnapshot, LegSnapshot
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


def mission_snapshot(name):
    """Expand committed synthetic scenario recipes into immutable real projections."""
    spec = fixture(name)
    legs, records = [], []
    for number, recipe in enumerate(spec["legs"], 1):
        delta = timedelta(hours=recipe["departureShiftHours"])

        def shift(value, delta=delta):
            if isinstance(value, dict):
                return {key: shift(v) for key, v in value.items()}
            if isinstance(value, list):
                return [shift(v) for v in value]
            if isinstance(value, str) and len(value) >= 20 and value.endswith("Z"):
                try:
                    return (utc(value) + delta).isoformat().replace("+00:00", "Z")
                except ValueError:
                    pass
            return value

        data = shift(fixture(recipe["base"]))
        raw = data["mission"]["legs"][0]
        raw["id"] = f"{name}-leg-{number}"
        data["timeline"]["mission_leg_id"] = raw["id"]
        if recipe.get("denseTransitions"):
            # Continuous Ka risk plus alternating Starshield outages: no quiet filler.
            data["source_records"] = [
                r
                for r in data["source_records"]
                if r["source_type"] == "availability_basis"
            ]
            start, end = map(utc, data["utc_bounds"])

            def outage(transport, a, b, ordinal, leg_id=raw["id"]):
                return {
                    "source_id": f"{leg_id}-{transport}-{ordinal}",
                    "source_type": "configured_outage",
                    "transport": transport,
                    "state": "offline",
                    "start_time": a.isoformat(),
                    "end_time": b.isoformat(),
                    "reason": "Synthetic configured risk",
                    "source_revision": "mission-fixture-v1",
                }

            data["source_records"].append(outage("Ka", start, end, 0))
            count = recipe["denseTransitions"]
            for index in range(0, count, 2):
                a = start + (end - start) * index / count
                b = start + (end - start) * (index + 1) / count
                data["source_records"].append(outage("Ku", a, b, index))
        legs.append(snapshot(data))
        records.append(data)
    metadata = {
        "id": name,
        "name": "Synthetic mission continuation qualification",
        "legs": [json.loads(l.leg_json) for l in legs],
    }
    return ExportSnapshot(
        name,
        sha256(canonical_json(records)).hexdigest(),
        canonical_json(metadata),
        tuple(legs),
        (),
        (),
    )
