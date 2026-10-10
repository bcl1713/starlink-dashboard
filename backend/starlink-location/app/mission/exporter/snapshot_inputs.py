"""Short capture of committed inputs; no preparation, publication or disk writes."""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree as ET

from app.mission import storage, timeline_service
from app.mission.models import Mission
from app.satellites.catalog import get_satellite_catalog, load_satellite_catalog
from app.satellites.coverage import CoverageSampler
from app.satellites.kmz_importer import (
    extract_polygon_from_kml,
    polygon_to_geojson_feature,
)
from app.satellites.rules import ConstraintConfig


def canonical_json(value: object) -> bytes:
    """Serialize once without retaining references to mutable input graphs."""

    def encode(item):
        if isinstance(item, datetime):
            return item.isoformat()
        if isinstance(item, Path):
            return str(item)
        raise TypeError(f"Unsupported snapshot value: {type(item).__name__}")

    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=encode
    ).encode()


@dataclass(frozen=True)
class SourcePayload:
    name: str
    content: bytes

    @property
    def digest(self) -> str:
        return sha256(self.content).hexdigest()


class SnapshotCaptureError(RuntimeError):
    """Committed export inputs were missing or could not be captured consistently."""


def _coverage_inputs(*, persisted: bool = False) -> tuple[SourcePayload, ...]:
    # Preserve legacy precedence, including an already loaded default sampler.
    sampler = None if persisted else timeline_service._COVERAGE_SAMPLER
    if sampler is not None:
        return (
            SourcePayload(
                "coverage/sampler",
                canonical_json(
                    {
                        "data": sampler.coverage_data,
                        "polygons": sampler.satellite_polygons,
                    }
                ),
            ),
        )
    path = Path("data/sat_coverage/commka.geojson")
    if path.exists():
        return (SourcePayload("coverage/geojson", path.read_bytes()),)
    for path in (
        Path("data/sat_coverage/CommKa.kmz"),
        timeline_service.APP_DIR / "satellites/assets/CommKa.kmz",
    ):
        if path.exists():
            return (SourcePayload("coverage/kmz", path.read_bytes()),)
    return (SourcePayload("coverage/missing", b"null"),)


def _read_dependencies(
    mission: Mission, route_manager, poi_manager, *, persisted: bool = False
) -> tuple[SourcePayload, ...]:
    sources = []
    from app.mission.planning.models import PlanningManifest
    from app.mission.planning.sources import SourceStore, _records, source_closure

    raw = mission.metadata.get("itinerary_planning")
    manifest = PlanningManifest.model_validate(raw) if raw is not None else None
    closure = source_closure(mission, manifest)
    if closure and route_manager is None:
        raise SnapshotCaptureError("Planning source storage is unavailable")
    if manifest is not None:
        store = SourceStore(storage.MISSIONS_DIR, route_manager.routes_dir)
        for source in closure:
            content = store.path(source).read_bytes()
            if sha256(content).hexdigest() != source.content_hash:
                raise SnapshotCaptureError("Retained source content changed")
            sources.append(
                SourcePayload(f"package/planning/{source.owned_relative_path}", content)
            )
            if source.kind == "route_kml":
                store.resolve_profile(source.id)
                sources.append(
                    SourcePayload(
                        f"package/routes/{source.id}.profile.json",
                        store.descriptor_path(source.id).read_bytes(),
                    )
                )
        for reference in manifest.proposal_refs:
            content = (
                store.root.parent
                / mission.id
                / "planning"
                / "proposals"
                / f"{reference.id}.json"
            ).read_bytes()
            if sha256(content).hexdigest() != reference.payload_hash:
                raise SnapshotCaptureError("Retained proposal payload changed")
            sources.append(
                SourcePayload(
                    f"package/planning/proposals/{reference.id}.json", content
                )
            )
    route_ids = dict.fromkeys(leg.route_id for leg in mission.legs if leg.route_id)
    if manifest:
        route_ids.update(
            {
                record["route_id"]: None
                for record in _records(manifest.storage_record())
                if record.get("route_id")
            }
        )
        route_ids.update({s.id: None for s in closure if s.kind == "route_kml"})
    for route_id in route_ids:
        route = route_manager.get_route(route_id) if route_manager else None
        sources.append(
            SourcePayload(
                f"route/{route_id}",
                canonical_json(route.model_dump(mode="json") if route else None),
            )
        )
        kml = (
            Path(route_manager.routes_dir) / f"{route_id}.kml"
            if route_manager
            else None
        )
        sources.append(
            SourcePayload(f"kml/{route_id}", kml.read_bytes())
            if kml and kml.exists()
            else SourcePayload(f"kml_missing/{route_id}", b"")
        )
        if manifest and not (kml and kml.exists()):
            raise SnapshotCaptureError(f"Retained route {route_id} is missing")
    # All POIs are necessary: mission exports include global satellite POIs and
    # preparation resolves global X positions as well as mission-scoped markers.
    sources.append(
        SourcePayload(
            "pois",
            canonical_json(
                [
                    poi.model_dump(mode="json")
                    | {
                        name: getattr(poi, name)
                        for name, field in type(poi).model_fields.items()
                        if field.exclude
                    }
                    for poi in poi_manager.list_pois()
                ]
                if poi_manager
                else []
            ),
        )
    )
    if manifest is not None:
        pois = json.loads(next(p.content for p in sources if p.name == "pois"))
        sources.append(
            SourcePayload(
                "package/pois/retained.json",
                canonical_json(
                    {
                        "pois": [
                            poi for poi in pois if poi.get("mission_id") == mission.id
                        ]
                    }
                ),
            )
        )
    sources.append(
        SourcePayload(
            "catalog",
            canonical_json(
                [
                    asdict(satellite)
                    for satellite in (
                        load_satellite_catalog(read_only=True)
                        if persisted
                        else get_satellite_catalog(read_only=True)
                    ).list_all()
                ]
            ),
        )
    )
    sources.append(
        SourcePayload("constraints", canonical_json(asdict(ConstraintConfig())))
    )
    from app.services.ground_entry_point import get_cached_ground_entry_point

    ground_entry = get_cached_ground_entry_point()
    sources.append(
        SourcePayload(
            "ground_entry",
            canonical_json(asdict(ground_entry) if ground_entry else None),
        )
    )
    sources.extend(
        _coverage_inputs(persisted=True) if persisted else _coverage_inputs()
    )
    for leg in mission.legs:
        try:
            timeline = storage.load_mission_timeline(
                leg.id, parent_mission_id=mission.id
            )
            content = canonical_json(
                timeline.model_dump(mode="json") if timeline else None
            )
        except (OSError, ValueError, TypeError) as exc:
            # A corrupt optional cache must not prevent a successful rebuild.
            content = canonical_json({"cache_error": type(exc).__name__})
        sources.append(SourcePayload(f"cache/{leg.id}", content))
    return tuple(sources)


def capture_inputs(mission_id: str, route_manager, poi_manager, *, persisted=False):
    """Lock order matches saves; recheck mutable dependencies before release."""
    last_error = None
    for attempt in range(2):
        try:
            with storage.get_active_leg_lock(), storage.get_mission_lock(mission_id):
                mission = storage.load_mission_v2(mission_id)
                if mission is None:
                    raise SnapshotCaptureError(f"Mission {mission_id} not found")
                metadata = canonical_json(mission.model_dump(mode="json"))
                options = {"persisted": True} if persisted else {}
                first = _read_dependencies(
                    mission, route_manager, poi_manager, **options
                )
                second = _read_dependencies(
                    mission, route_manager, poi_manager, **options
                )
                if first == second:
                    warnings = (
                        (
                            "Source inputs changed during capture; whole-capture retry succeeded.",
                        )
                        if attempt
                        else ()
                    )
                    return metadata, first, warnings
        except SnapshotCaptureError:
            raise
        except (OSError, ValueError, RuntimeError, TypeError) as exc:
            last_error = exc
    if last_error is not None:
        raise SnapshotCaptureError(
            "Source inputs unavailable during capture after one retry"
        ) from last_error
    raise SnapshotCaptureError("Source inputs changed during both capture attempts")


def captured_coverage(sources: tuple[SourcePayload, ...]) -> CoverageSampler | None:
    """Decode captured defaults after releasing capture locks, entirely in memory."""
    payload = next(item for item in sources if item.name.startswith("coverage/"))
    if payload.name == "coverage/missing":
        return None
    if payload.name == "coverage/sampler":
        data = json.loads(payload.content)
        sampler = CoverageSampler()
        sampler.coverage_data = data["data"]
        sampler.satellite_polygons = data["polygons"]
        return sampler
    if payload.name == "coverage/geojson":
        return CoverageSampler.from_geojson(json.loads(payload.content))
    with zipfile.ZipFile(io.BytesIO(payload.content)) as archive:
        names = archive.namelist()
        name = next((n for n in ("doc.kml", "Document.kml") if n in names), None)
        name = name or next(n for n in names if n.endswith(".kml"))
        root = ET.fromstring(archive.read(name))
    features = []
    for polygon_name, satellite_id in (
        ("PORB", "POR"),
        ("PORA", "POR"),
        ("IOR", "IOR"),
        ("AOR", "AOR"),
    ):
        coords = extract_polygon_from_kml(root, polygon_name)
        if coords:
            features.append(
                polygon_to_geojson_feature(
                    coords,
                    satellite_id,
                    {
                        "satellite_id": satellite_id,
                        "coverage_region": polygon_name,
                    },
                )
            )
    if not features:
        raise ValueError("Captured CommKa KMZ has no coverage polygons")
    return CoverageSampler.from_geojson(
        {"type": "FeatureCollection", "features": features}
    )


def capture_default_coverage() -> CoverageSampler | None:
    """Read-only default discovery for legacy callers without snapshot context."""
    return captured_coverage(_coverage_inputs())
