"""Reconstruct effective routes from package profiles and retained canonical evidence."""

import json
import zipfile
from datetime import datetime, timezone
from hashlib import sha256
from types import SimpleNamespace


def utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def package_snapshots(path, temporary, source_hashes):
    from app.mission.effective_route import prepare_effective_route
    from app.mission.exporter.customer_projection import BriefingInterval, BriefingLeg
    from app.mission.exporter.snapshot import LegSnapshot
    from app.mission.exporter.snapshot_inputs import canonical_json
    from app.mission.models import Mission
    from app.mission.storage import _ordered_mission
    from app.services.kml_parser import parse_kml_file

    with zipfile.ZipFile(path) as archive:
        metadata = json.loads(archive.read("mission.json"))
        metadata["legs"] = [
            json.loads(archive.read(name))
            for name in sorted(archive.namelist())
            if name.startswith("legs/") and name.endswith(".json")
        ]
        mission = _ordered_mission(Mission.model_validate(metadata))
        evidence = json.loads(
            archive.read("exports/mission/mission-customer-briefing-evidence.json")
        )
        if mission.id != evidence["missionId"]:
            raise ValueError("Retained canonical evidence belongs to another mission")
        by_leg = {leg["legId"]: leg["canonical"] for leg in evidence["legs"]}
        for number, leg in enumerate(mission.legs):
            raw = archive.read(f"routes/{leg.route_id}.kml")
            source_hash = sha256(raw).hexdigest()
            if source_hash not in source_hashes:
                raise ValueError(
                    "Package KML is not one of the immutable original inputs"
                )
            profile_path = f"routes/{leg.route_id}.profile.json"
            profile = (
                json.loads(archive.read(profile_path))
                if profile_path in archive.namelist()
                else {}
            )
            if profile and profile["source_hash"] != source_hash:
                raise ValueError("Route ingestion descriptor hash mismatch")
            source = temporary / f"source-{number}.kml"
            source.write_bytes(raw)
            route = parse_kml_file(
                source, profile=profile.get("ingestion_profile", "legacy")
            )
            route.metadata.file_path = f"{leg.route_id}.kml"
            manager = SimpleNamespace(
                get_route=lambda key, route=route, route_id=leg.route_id: (
                    route if key == route_id else None
                )
            )
            route = prepare_effective_route(leg, manager)
            canonical = by_leg[leg.id]
            bounds = tuple(utc(value) for value in canonical["utcBounds"])
            intervals = tuple(
                BriefingInterval(
                    row["id"],
                    index,
                    utc(row["startUtc"]),
                    utc(row["endUtc"]),
                    (),
                    row["posture"],
                    tuple(row["restrictions"]),
                    tuple(row["sourceIds"]),
                    tuple(row["causes"]),
                    tuple(row["limitations"]),
                    tuple(row["remainingTransports"]),
                )
                for index, row in enumerate(canonical["intervals"], 1)
            )
            rows = tuple(
                row
                for row in intervals
                if row.restrictions or row.posture != "Nominal" or row.limitations
            )
            captured = LegSnapshot(
                leg.id,
                canonical_json(leg.model_dump(mode="json")),
                canonical_json(route.model_dump(mode="json")),
                None,
                (),
                (),
                bounds,
                "rebuilt",
                (),
            )
            projection = BriefingLeg(
                leg.id,
                bounds,
                intervals,
                rows,
                (),
                tuple(canonical["notes"]),
                "Retained canonical evidence",
                None,
            )
            yield captured, projection
