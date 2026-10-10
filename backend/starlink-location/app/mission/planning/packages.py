"""Validated immutable package graphs and atomic collision-safe publication."""

import hashlib
import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from uuid import uuid4
from zipfile import ZipFile

from app.mission import storage
from app.mission.models import Mission
from app.models.poi import POI
from app.models.route import ParsedRoute
from app.services.kml_parser import parse_kml_file

from .errors import conflict
from .journal import json_bytes
from .match import resolve_anchor
from .models import PlanningDraft, PlanningManifest, PlanningProposal, PlanningView
from .sources import (
    SourceStore,
    _graph_references,
    _records,
    _reference_graphs,
    route_references,
    source_closure,
)
from .types import RouteAnchor


@dataclass(frozen=True)
class PackageImportPlan:
    mission_json: bytes
    manifest_json: bytes | None
    files: tuple[tuple[str, bytes | None], ...]
    before: tuple[tuple[str, bytes | None], ...]
    routes: tuple[bytes, ...]
    pois: tuple[bytes, ...]
    replaced_pois: tuple[bytes, ...]
    remaps: tuple[tuple[str, str], ...]
    target_json: bytes | None
    _sources: SourceStore = field(repr=False, compare=False)


def _poi_record(poi):
    return poi.model_dump(mode="json") | {
        name: getattr(poi, name)
        for name, field in type(poi).model_fields.items()
        if field.exclude
    }


def _selector(value):
    if (
        not isinstance(value, str)
        or not value
        or value in {".", ".."}
        or "/" in value
        or "\\" in value
        or "\x00" in value
    ):
        raise ValueError("Invalid package resource selector")
    return value


def _safe_archive(zf):
    names = zf.namelist()
    if len(set(names)) != len(names):
        raise ValueError("Duplicate package entries")
    for name in names:
        path = PurePosixPath(name)
        if (
            not name
            or path.is_absolute()
            or ".." in path.parts
            or "\\" in name
            or "\x00" in name
        ):
            raise ValueError("Invalid archive path")
        info = zf.getinfo(name)
        if (info.external_attr >> 16) & 0o170000 == 0o120000:
            raise ValueError("Archive symlinks are forbidden")
    if "mission.json" not in names:
        raise ValueError("Invalid package: missing mission.json")


def _remap(value, routes, old_owner, new_owner, key=None):
    if isinstance(value, dict):
        result = {
            k: _remap(v, routes, old_owner, new_owner, k) for k, v in value.items()
        }
        if (
            value.get("kind") in {"route_kml", "itinerary_pdf"}
            and "owned_relative_path" in value
        ):
            result["id"] = routes.get(value["id"], value["id"])
            suffix = "kml" if value["kind"] == "route_kml" else "pdf"
            result["owned_relative_path"] = f"sources/{result['id']}.{suffix}"
        return result
    if isinstance(value, list):
        return [_remap(v, routes, old_owner, new_owner, key) for v in value]
    if isinstance(value, str):
        embedded = {
            "route_json": ParsedRoute,
            "anchor_route_json": ParsedRoute,
            "structural_draft_json": PlanningDraft,
        }
        if key in embedded:
            try:
                decoded = json.loads(value)
                embedded[key].model_validate(decoded)
                return json.dumps(
                    _remap(decoded, routes, old_owner, new_owner),
                    sort_keys=True,
                    separators=(",", ":"),
                )
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    f"Invalid embedded planning {key}; restore a valid package"
                ) from exc
        if key in {"route_id", "source_id", "source_ids"}:
            return routes.get(value, value)
        if key in {"mission_id", "owner"} and value == old_owner:
            return new_owner
    return value


def _parse_routes(payloads, profiles):
    result = {}
    # Parsing uses an owned temporary directory and leaves no staged files behind.
    with tempfile.TemporaryDirectory(prefix="planning-package-") as directory:
        for route_id, data in payloads.items():
            path = Path(directory) / f"{_selector(route_id)}.kml"
            path.write_bytes(data)
            route = parse_kml_file(path, profile=profiles.get(route_id, "legacy"))
            if route is None:
                raise ValueError(f"Invalid packaged route {route_id}")
            result[route_id] = route
    return result


def _validate_anchors(graph, routes):
    for record in _records(graph):
        if "occurrence_id" in record and "segment_index" in record:
            anchor = RouteAnchor.model_validate(record)
            route = routes.get(anchor.route_id)
            if route is None:
                raise ValueError("Anchor references an absent route")
            resolve_anchor(anchor, route)


def _retained_target(target, mission, manifest, sources, source_bytes):
    """A checked replacement must contain all work that the target retains."""
    raw = target.metadata.get("itinerary_planning")
    if raw is None:
        return set()
    current = PlanningManifest.model_validate(raw)
    message = (
        "Archive would discard retained mission work; import as a new mission instead"
    )
    if manifest is None:
        raise ValueError(message)
    for name in (
        "source_revisions",
        "proposals",
        "proposal_refs",
        "leg_history",
        "review_records",
    ):
        if any(
            record not in getattr(manifest, name) for record in getattr(current, name)
        ):
            raise ValueError(message)
    bindings = manifest.route_bindings + manifest.route_history
    bindings += [leg.route for leg in manifest.expected_legs if leg.route]
    if any(
        binding not in bindings
        for binding in current.route_bindings + current.route_history
    ):
        raise ValueError(message)
    retained_legs = manifest.expected_legs + [
        history.leg for history in manifest.leg_history
    ]
    if any(leg not in retained_legs for leg in current.expected_legs):
        raise ValueError(message)
    installed = mission.legs + [
        history.installed_leg
        for history in manifest.leg_history
        if history.installed_leg
    ]
    if any(
        leg.model_dump(exclude={"is_active"})
        not in [item.model_dump(exclude={"is_active"}) for item in installed]
        for leg in target.legs
    ):
        raise ValueError(message)
    if (
        current.itinerary_baseline != manifest.itinerary_baseline
        or target.name != mission.name
        or target.description != mission.description
        or {k: v for k, v in target.metadata.items() if k != "itinerary_planning"}
        != {k: v for k, v in mission.metadata.items() if k != "itinerary_planning"}
    ):
        raise ValueError(message)
    reusable = set()
    for source in source_closure(target, current):
        if sources.path(source).read_bytes() != source_bytes[source.id]:
            raise ValueError("Target owned bytes changed")
        if source.kind == "route_kml":
            if route_references(
                source.id, sources=sources, excluding_mission=target.id
            ):
                raise ValueError(
                    "Target route has foreign references; import as a new mission"
                )
            if sources.resolve_profile(source.id) != "planning_v1":
                raise ValueError("Target source ownership profile is unavailable")
        reusable.add(source.id)
    return reusable


def stage_package(
    zf: ZipFile, target: Mission | None, sources: SourceStore
) -> PackageImportPlan:
    """Validate all archive bytes before preparing any publication side effect."""
    _safe_archive(zf)
    store = sources._store
    if store is None:
        raise ValueError("Package import requires a bound source commit context")
    sources.bind_store(store)
    if store.root != storage.MISSIONS_DIR.resolve():
        raise ValueError("Package commit context root changed")
    mission = Mission.model_validate_json(zf.read("mission.json"))
    _selector(mission.id)
    for leg in mission.legs:
        _selector(leg.id)
    raw = mission.metadata.get("itinerary_planning")
    manifest = PlanningManifest.model_validate(raw) if raw is not None else None
    closure = source_closure(mission, manifest)
    payloads = {
        PurePosixPath(n).stem: zf.read(n)
        for n in zf.namelist()
        if n.startswith("routes/") and n.endswith(".kml")
    }
    profiles, source_bytes, proposals = {}, {}, {}
    for source in closure:
        _selector(source.id)
        data = (
            zf.read(f"planning/{source.owned_relative_path}")
            if f"planning/{source.owned_relative_path}" in zf.namelist()
            else None
        )
        if data is None or hashlib.sha256(data).hexdigest() != source.content_hash:
            raise ValueError("Missing or changed retained source bytes")
        source_bytes[source.id] = data
        if source.kind == "route_kml":
            descriptor_path = f"routes/{source.id}.profile.json"
            if descriptor_path not in zf.namelist() or json.loads(
                zf.read(descriptor_path)
            ) != {
                "version": 1,
                "route_id": source.id,
                "source_hash": source.content_hash,
                "owner": mission.id,
                "ingestion_profile": "planning_v1",
            }:
                raise ValueError("Missing or invalid owned ingestion profile")
            if payloads.get(source.id) != data:
                raise ValueError("Owned route bytes are missing or inconsistent")
            profiles[source.id] = "planning_v1"
    for record in _records(mission.model_dump(mode="json")):
        route_id = record.get("route_id")
        if route_id and route_id not in payloads:
            raise ValueError(f"Referenced route {route_id} missing from package")
    if manifest:
        for reference in manifest.proposal_refs:
            _selector(reference.id)
            name = f"planning/proposals/{reference.id}.json"
            if name not in zf.namelist():
                raise ValueError("Referenced proposal missing from package")
            data = zf.read(name)
            proposal = PlanningProposal.model_validate_json(data)
            if (
                hashlib.sha256(data).hexdigest() != reference.payload_hash
                or proposal.id != reference.id
                or proposal.input_identity != reference.input_identity
                or proposal.expected_revision != reference.expected_revision
            ):
                raise ValueError("Proposal payload does not match its reference")
            proposals[reference.id] = proposal.model_dump(mode="json")
    parsed = _parse_routes(payloads, profiles)
    _validate_anchors(mission.model_dump(mode="json"), parsed)
    for proposal in proposals.values():
        _validate_anchors(proposal, parsed)
    with storage.get_active_leg_lock():
        if target is not None and target.id != mission.id:
            raise ValueError("Import target does not match archive mission")
        old_owner = mission.id
        existing = storage.load_mission_v2(mission.id)
        if target is not None:
            if existing is None or existing != target:
                raise conflict("Import target changed during staging")
            if any(leg.is_active for leg in existing.legs):
                raise conflict("Deactivate mission legs before importing")
        elif existing is not None:
            mission.id = str(uuid4())
        reusable = (
            _retained_target(target, mission, manifest, sources, source_bytes)
            if target
            else set()
        )
        remaps = {}
        for identity in set(payloads) | set(source_bytes):
            _selector(identity)
            if identity in reusable:
                continue
            if any(
                p.exists()
                for p in (
                    sources.routes_dir / f"{identity}.kml",
                    sources.root / "sources" / f"{identity}.pdf",
                    sources.root / "sources" / f"{identity}.kml",
                    sources.root / "inventory" / f"{identity}.json",
                )
            ):
                remaps[identity] = str(uuid4())
        raw = _remap(mission.model_dump(mode="json"), remaps, old_owner, mission.id)
        raw["id"] = mission.id
        for leg in raw["legs"]:
            leg["is_active"] = False
        mission = Mission.model_validate(raw)
        manifest = (
            PlanningManifest.model_validate(mission.metadata["itinerary_planning"])
            if manifest
            else None
        )
        if manifest:
            if target and target.metadata.get("itinerary_planning"):
                manifest.revision = (
                    target.metadata["itinerary_planning"]["revision"] + 1
                )
            for history in manifest.leg_history:
                if history.installed_leg:
                    history.installed_leg.is_active = False
            for reference in manifest.proposal_refs:
                data = json_bytes(
                    _remap(proposals[reference.id], remaps, old_owner, mission.id)
                )
                proposals[reference.id] = data
                reference.payload_hash = hashlib.sha256(data).hexdigest()
                if reference.expected_revision != manifest.revision:
                    reference.state = "stale"
            mission.metadata["itinerary_planning"] = manifest.storage_record()
        mission = storage._ordered_mission(mission)
        files = {}
        remapped_routes = []
        for old_id, content in payloads.items():
            new_id = remaps.get(old_id, old_id)
            path = sources.routes_dir / f"{new_id}.kml"
            files[path] = content
            route = parsed[old_id].model_copy(deep=True)
            route.route_id = new_id
            route.metadata.file_path = str(path)
            remapped_routes.append(route.model_dump_json().encode())
        for source in (manifest.source_revisions if manifest else []):
            old_id = next(
                (old for old, new in remaps.items() if new == source.id), source.id
            )
            files[sources.path(source)] = source_bytes[old_id]
            if source.kind == "route_kml":
                files[sources.root / "inventory" / f"{source.id}.json"] = json_bytes(
                    source.storage_record()
                )
                files[sources.descriptor_path(source.id)] = json_bytes(
                    {
                        "version": 1,
                        "route_id": source.id,
                        "source_hash": source.content_hash,
                        "owner": mission.id,
                        "ingestion_profile": "planning_v1",
                    }
                )
        for identity, data in proposals.items():
            files[
                store.root / mission.id / "planning" / "proposals" / f"{identity}.json"
            ] = data
        files[storage.get_mission_file_path(mission.id)] = json_bytes(
            mission.model_copy(update={"legs": []}).model_dump(mode="json")
        )
        for leg in mission.legs:
            files[storage.get_mission_leg_file_path(mission.id, leg.id)] = (
                leg.model_dump_json().encode()
            )
        if target:
            for old in target.legs:
                if old.id not in {leg.id for leg in mission.legs}:
                    files[storage.get_mission_leg_file_path(mission.id, old.id)] = None
                files[storage.get_leg_timeline_path(old.id, mission.id)] = None
        pois = {}
        for name in zf.namelist():
            if not name.startswith("pois/") or not name.endswith(".json"):
                continue
            for raw_poi in json.loads(zf.read(name)).get("pois", []):
                poi = POI.model_validate(raw_poi)
                if poi.category == "satellite":
                    if (
                        poi.mission_id is not None
                        or poi.route_id is not None
                        or poi.generated_source is not None
                    ):
                        raise ValueError(
                            "Packaged satellite must be global and unmanaged"
                        )
                    if store.poi_manager.find_global_poi_by_name(poi.name):
                        continue  # Existing current dependencies remain authoritative.
                    poi.id = str(uuid4())
                    pois.setdefault(raw_poi["id"], json_bytes(_poi_record(poi)))
                    continue
                if poi.mission_id not in {None, old_owner} or poi.route_id not in {
                    None,
                    *payloads,
                }:
                    raise ValueError("Packaged POI is outside imported ownership scope")
                key = poi.id
                remapped = _remap(raw_poi, remaps, old_owner, mission.id)
                remapped.update(id=str(uuid4()), mission_id=mission.id)
                pois.setdefault(
                    key, json_bytes(_poi_record(POI.model_validate(remapped)))
                )
        from app.mission.routes_v2 import _endpoint_marker

        replaced = []
        for leg in (target.legs if target else []):
            markers = {
                _endpoint_marker(leg.id, role) for role in ("departure", "arrival")
            }
            for poi in store.poi_manager.list_pois(
                route_id=leg.route_id, mission_id=target.id
            ):
                if poi.description in markers:
                    replaced.append(json_bytes(_poi_record(poi)))
        route_models = {
            r.route_id: r
            for r in (ParsedRoute.model_validate_json(data) for data in remapped_routes)
        }
        # Validate preserved installed and historical snapshots against the actual
        # remapped immutable geometry. Never accept an unusable Reviewed clone.
        from app.mission.effective_route import prepare_effective_route

        from .canonical import canonical_inputs

        installed = list(mission.legs)
        if manifest:
            installed.extend(
                h.installed_leg for h in manifest.leg_history if h.installed_leg
            )
        route_view = SimpleNamespace(get_route=route_models.get)
        for leg in installed:
            if leg.transports.planning_inputs is not None:
                effective = prepare_effective_route(leg, route_view)
                canonical_inputs(leg, effective)
        for leg in mission.legs:
            route = route_models.get(leg.route_id)
            if route is None or not route.points:
                continue
            for role, icon, point in (
                ("departure", "airport", route.points[0]),
                ("arrival", "flag", route.points[-1]),
            ):
                marker = _endpoint_marker(leg.id, role)
                pois = {
                    key: value
                    for key, value in pois.items()
                    if json.loads(value).get("description") != marker
                }
                poi = POI(
                    id=str(uuid4()),
                    name=f"{leg.name} {role.title()}",
                    latitude=point.latitude,
                    longitude=point.longitude,
                    icon=icon,
                    category=role,
                    description=marker,
                    route_id=leg.route_id,
                    mission_id=mission.id,
                )
                pois[poi.id] = json_bytes(_poi_record(poi))
        # Storage's normal configured root may be relative to the process cwd.
        # Make trusted destinations absolute without resolving away aliases.
        absolute_files = {path.absolute(): data for path, data in files.items()}
        if len(absolute_files) != len(files):
            raise ValueError("Duplicate import destination")
        files = absolute_files
        if any(p.resolve() != p for p in files):
            raise ValueError("Import destinations cannot contain filesystem aliases")
        before = tuple((str(p), p.read_bytes() if p.exists() else None) for p in files)
        return PackageImportPlan(
            mission.model_dump_json().encode(),
            json_bytes(manifest.storage_record()) if manifest else None,
            tuple((str(p), data) for p, data in files.items()),
            before,
            tuple(remapped_routes),
            tuple(pois.values()),
            tuple(replaced),
            tuple(remaps.items()),
            target.model_dump_json().encode() if target else None,
            sources,
        )


def commit_package(
    plan: PackageImportPlan, expected_revision: int | None
) -> PlanningView:
    sources = plan._sources
    store = sources._store
    if store is None:
        raise ValueError("Package commit context is unavailable")
    sources.bind_store(store)
    if store.root != storage.MISSIONS_DIR.resolve():
        raise ValueError("Package commit context root changed")
    mission = Mission.model_validate_json(plan.mission_json)
    manifest = (
        PlanningManifest.model_validate_json(plan.manifest_json)
        if plan.manifest_json
        else None
    )
    with storage.get_active_leg_lock(), storage.get_mission_lock(mission.id):
        graphs = _reference_graphs(sources)
        current = storage.load_mission_v2(mission.id)
        if plan.target_json is None:
            if current is not None or expected_revision is not None:
                raise conflict("Import destination is no longer empty")
        else:
            target = Mission.model_validate_json(plan.target_json)
            if current != target or any(leg.is_active for leg in current.legs):
                raise conflict("Import destination changed")
            current_manifest = current.metadata.get("itinerary_planning")
            if current_manifest and current_manifest["revision"] != expected_revision:
                raise conflict()
        for path, before in plan.before:
            p = Path(path)
            if p.resolve() != p or (p.read_bytes() if p.exists() else None) != before:
                raise conflict("Import source destination changed")
        routes = {
            r.route_id: r
            for r in (ParsedRoute.model_validate_json(data) for data in plan.routes)
        }
        if any(
            _graph_references(graphs, route_id, excluding_mission=mission.id)
            for route_id in routes
        ):
            raise conflict("A foreign mission now references an import destination")
        if store.route_manager.get_active_route_id() in routes:
            raise conflict("An import destination became active")
        pois = {
            p.id: _poi_record(p)
            for p in (POI.model_validate_json(data) for data in plan.pois)
        }
        replaced = {
            p.id: _poi_record(p)
            for p in (POI.model_validate_json(data) for data in plan.replaced_pois)
        }
        current_pois = {p.id: _poi_record(p) for p in store.poi_manager.list_pois()}
        if any(current_pois.get(key) != poi for key, poi in replaced.items()):
            raise conflict("Import endpoint ownership changed")
        if set(pois) & {p.id for p in store.poi_manager.list_pois()}:
            raise conflict("Import POI destination changed")
        if any(
            poi.get("category") == "satellite"
            and store.poi_manager.find_global_poi_by_name(poi["name"])
            for poi in pois.values()
        ):
            raise conflict("Current satellite dependencies changed during import")
        scope = {
            "imported": {
                key: {
                    field: poi.get(field)
                    for field in (
                        "mission_id",
                        "route_id",
                        "generated_source",
                        "description",
                        "category",
                        "name",
                    )
                }
                for key, poi in {**replaced, **pois}.items()
            }
        }
        try:
            store.journal.commit(
                {Path(path): data for path, data in plan.files},
                poi_scope=scope if pois else None,
                pois=pois,
            )
        finally:
            if not any(store.journal.directory.glob("*.json")):
                store.poi_manager.reload_pois()
        store.route_manager._routes.update(routes)
        from app.mission.slide_cache.coordinator import saved_mission

        saved_mission(current, mission)
        if manifest:
            return store._view(mission, manifest)
        return PlanningView(mission=mission, revision=1, expected_legs=[], errors=[])
