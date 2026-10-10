"""Effective per-leg inputs, renderer identity, and safe JSON serialization."""

import base64
import json
from dataclasses import asdict, replace
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from app.mission.exporter.snapshot import ExportSnapshot, LegSnapshot
from app.mission.exporter.snapshot_inputs import SourcePayload, canonical_json

BOOKKEEPING = {"created_at", "updated_at", "imported_at", "is_active"}


def effective(value):
    if isinstance(value, dict):
        return {k: effective(v) for k, v in value.items() if k not in BOOKKEEPING}
    if isinstance(value, list):
        return [effective(v) for v in value]
    return value


def renderer_revision():
    # Hash the shipped renderer, Python preparation code, and brand assets.
    root = Path(__file__).resolve().parents[1]
    paths = list(root.parent.rglob("*.py")) + list((root / "assets").glob("*"))
    deployed = Path("/opt/customer-briefing/renderer")
    if deployed.exists():
        renderer = deployed
    else:
        renderer = root.parents[3] / "frontend/mission-planner/src/mission-export"
    paths += list(renderer.rglob("*.mjs")) + list(renderer.rglob("*.css"))
    assets = Path("/opt/customer-briefing/assets")
    if assets.exists():
        paths += [p for p in assets.rglob("*") if p.is_file()]
    digest = sha256(b"customer-leg-cache-v1")
    for path in sorted(paths):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def leg_inputs(metadata, sources, leg_id, revision):
    raw = json.loads(metadata)
    from app.mission.planning.models import PlanningManifest
    from app.mission.planning.order import project_leg_order

    manifest = raw.get("metadata", {}).get("itinerary_planning")
    order = project_leg_order(
        PlanningManifest.model_validate(manifest) if manifest is not None else None,
        tuple(leg["id"] for leg in raw["legs"]),
    )
    number = order.numbers[leg_id]
    leg = next(l for l in raw["legs"] if l["id"] == leg_id)
    route_id = leg.get("route_id")
    selected = tuple(
        s
        for s in sources
        if (
            not s.name.startswith(("route/", "kml/", "kml_missing/", "cache/"))
            or s.name
            in {
                f"route/{route_id}",
                f"kml/{route_id}",
                f"kml_missing/{route_id}",
                f"cache/{leg_id}",
            }
        )
    )
    selected = tuple(
        (
            replace(
                source,
                content=canonical_json(
                    [
                        poi
                        for poi in json.loads(source.content)
                        if poi.get("generated_source") != "mission-timeline"
                        and poi.get("route_id") in {None, route_id}
                        and poi.get("mission_id") in {None, raw["id"], leg_id}
                    ]
                ),
            )
            if source.name == "pois"
            else source
        )
        for source in selected
    )
    # Cached predictions are fallback inputs, but successful preparation does not
    # use their volatile generation timestamps. Strip only known bookkeeping.
    dependencies = []
    for source in selected:
        try:
            content = canonical_json(effective(json.loads(source.content)))
        except (ValueError, UnicodeDecodeError):
            content = source.content
        dependencies.append([source.name, sha256(content).hexdigest()])
    parent = {k: v for k, v in raw.items() if k != "legs"}
    fingerprint = sha256(
        canonical_json(
            [
                effective(parent),
                effective(leg),
                number,
                order.total_count,
                dependencies,
                revision,
            ]
        )
    ).hexdigest()
    raw["legs"] = [leg]
    inputs = encode_inputs(canonical_json(raw), selected, (), number, order.total_count)
    return fingerprint, inputs


def encode_inputs(metadata, sources, warnings=(), number=1, count=1):
    return canonical_json(
        {
            "metadata": json.loads(metadata),
            "sources": [
                [s.name, base64.b64encode(s.content).decode()] for s in sources
            ],
            "warnings": warnings,
            "number": number,
            "count": count,
        }
    )


def decode_inputs(value):
    raw = json.loads(value)
    return (
        canonical_json(raw["metadata"]),
        tuple(SourcePayload(n, base64.b64decode(c)) for n, c in raw["sources"]),
        tuple(raw["warnings"]),
        raw["number"],
        raw["count"],
    )


def encode_snapshot(snapshot):
    def encode(value):
        if isinstance(value, bytes):
            return {"bytes": base64.b64encode(value).decode()}
        if isinstance(value, datetime):
            return {"datetime": value.isoformat()}
        raise TypeError(type(value).__name__)

    return json.dumps(asdict(snapshot), default=encode, sort_keys=True).encode()


def decode_snapshot(value):
    def hook(item):
        if set(item) == {"bytes"}:
            return base64.b64decode(item["bytes"])
        if set(item) == {"datetime"}:
            return datetime.fromisoformat(item["datetime"])
        return item

    raw = json.loads(value, object_hook=hook)
    legs = []
    for leg in raw.pop("legs"):
        for key in (
            "source_records",
            "resolved_restrictions",
            "warnings",
            "map_pois",
            "utc_bounds",
        ):
            if leg.get(key) is not None:
                leg[key] = tuple(leg[key])
        legs.append(LegSnapshot(**leg))
    raw["legs"] = tuple(legs)
    raw["source_payloads"] = tuple(SourcePayload(**s) for s in raw["source_payloads"])
    raw["warnings"] = tuple(raw["warnings"])
    return ExportSnapshot(**raw)
