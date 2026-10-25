"""Short rechecked publication gate and one journal for legs, timelines and POIs."""

from datetime import datetime, timezone
from uuid import uuid4

from app.mission import storage
from app.models.poi import POI
from app.services.poi.manager import _route_geometry_hash

from .errors import PlanningFailure, conflict
from .journal import json_bytes
from .models import ReviewRecord
from .publication import publication_identity, publication_key, validate_batch


def _poi_records(artifacts):
    geometry = (
        _route_geometry_hash(artifacts.route)
        if any(poi._route_segment_index is not None for poi in artifacts.generated_pois)
        else None
    )
    records = {}
    for value in artifacts.generated_pois:
        poi = POI(
            id=str(uuid4()),
            **value.model_dump(),
            generated_source="mission-timeline",
            planned_route_segment_index=value._route_segment_index,
            planned_route_geometry_hash=geometry
        )
        record = poi.model_dump(mode="json")
        record.update(
            generated_source="mission-timeline",
            planned_route_segment_index=poi.planned_route_segment_index,
            planned_route_geometry_hash=poi.planned_route_geometry_hash,
        )
        records[poi.id] = record
    return records


def commit_reviewed_batch(store, mission_id, request, prepared):
    from .review import validate_review
    from .service import PlanningService

    validate_batch(request)
    if (
        prepared.expected_revision != request.expected_revision
        or len(prepared.entries) != len(request.entries)
        or any(
            (entry.leg_id, entry.review) != (captured.leg_id, captured.review)
            for entry, captured in zip(request.entries, prepared.entries)
        )
    ):
        raise conflict("Prepared batch does not match reviewed decisions")
    key, identity = publication_key(request), publication_identity(request)
    records, owned_ids = {}, set()
    for captured in prepared.entries:
        if (
            captured.input_identity != captured.review.input_identity
            or captured.artifacts.planning_evaluation != captured.evaluation
        ):
            raise conflict("Prepared evaluation does not match reviewed inputs")
        if captured.map_diagnostics:
            error = captured.map_diagnostics[0]
            raise PlanningFailure(422, error.code, error.message, action=error.action)
        if captured.artifacts.validated_leg is None:
            raise PlanningFailure(
                422, "validated_leg_required", "Validated executable leg is required"
            )
        owned = _poi_records(captured.artifacts)
        if owned_ids & set(owned):
            raise PlanningFailure(
                422, "poi_owner_mismatch", "Prepared marker IDs collide"
            )
        owned_ids.update(owned)
        records[captured.leg_id] = owned
    service = PlanningService(store)
    with storage.get_active_leg_lock(), storage.get_mission_lock(mission_id):
        mission, manifest = store._load(mission_id)
        previous = manifest.reviewed_publications.get(key)
        if previous is not None:
            if previous != identity:
                raise conflict("Publication key was used for different reviewed inputs")
            return store._view(mission, manifest)
        installed_ids, routes, entries = set(), set(), []
        for captured in prepared.entries:
            _, _, leg = store.checked(
                mission_id,
                captured.leg_id,
                request.expected_revision,
                captured.input_identity,
            )
            leg = next(
                leg for leg in manifest.expected_legs if leg.id == captured.leg_id
            )
            service.proposals._recheck(
                mission_id, leg.id, captured.review, captured.environment_identity
            )
            from app.mission.availability_context import selection_context

            validate_review(
                leg,
                captured.review,
                captured.evaluation,
                **selection_context(mission, leg, store.route_manager)
            )
            artifacts = captured.artifacts
            installed = artifacts.validated_leg.model_copy(deep=True)
            if (
                not leg.route
                or installed.is_active
                or installed.route_id != leg.route.route_id
                or artifacts.route.route_id != leg.route.route_id
                or artifacts.route.content_hash != leg.route.content_hash
                or artifacts.timeline.mission_leg_id != installed.id
                or (
                    leg.installed_leg_id is not None
                    and installed.id != leg.installed_leg_id
                )
            ):
                raise PlanningFailure(
                    422,
                    "artifact_binding_mismatch",
                    "Prepared artifacts do not match the reviewed inactive leg",
                )
            source = next(
                (
                    source
                    for source in manifest.source_revisions
                    if source.id == leg.route.source_id
                ),
                None,
            )
            if (
                source is None
                or source.owner != mission_id
                or source.content_hash != leg.route.content_hash
            ):
                raise PlanningFailure(
                    422,
                    "source_owner_mismatch",
                    "Route source is not owned by this mission",
                )
            store.sources.resolve_profile(installed.route_id)
            if installed.id in installed_ids or installed.route_id in routes:
                raise conflict(
                    "Selected executable IDs and generated marker scopes must be distinct"
                )
            if leg.installed_leg_id is None and any(
                item.id == installed.id for item in mission.legs
            ):
                raise conflict("Executable ID is already installed")
            if any(
                poi["mission_id"] != mission_id or poi["route_id"] != installed.route_id
                for poi in records[leg.id].values()
            ):
                raise PlanningFailure(
                    422,
                    "poi_owner_mismatch",
                    "Prepared markers belong to another scope",
                )
            installed_ids.add(installed.id)
            routes.add(installed.route_id)
            routes.update(
                item.route_id for item in mission.legs if item.id == installed.id
            )
            entries.append((leg, captured, installed))
        if any(
            item.id not in installed_ids and item.route_id in routes
            for item in mission.legs
        ):
            raise conflict(
                "Generated marker scopes cannot replace unrelated installed legs"
            )
        files, pois = {}, {}
        for leg, captured, installed in entries:
            leg.installed_leg_id = installed.id
            leg.review = ReviewRecord(
                **captured.review.model_dump(
                    exclude={"expected_revision", "idempotency_key"}
                ),
                saved_at=datetime.now(timezone.utc),
                environment_identity=captured.environment_identity
            )
            manifest.review_records.append(leg.review)
            files[
                storage.get_mission_leg_file_path(mission_id, installed.id).resolve()
            ] = json_bytes(installed.model_dump(mode="json"))
            files[storage.get_leg_timeline_path(installed.id, mission_id).resolve()] = (
                json_bytes(captured.artifacts.timeline.model_dump(mode="json"))
            )
            pois.update(records[leg.id])
        mission.legs = [leg for leg in mission.legs if leg.id not in installed_ids] + [
            installed for _, _, installed in entries
        ]
        manifest.reviewed_publications[key] = identity
        manifest.revision += 1
        return store.persist(
            mission,
            manifest,
            files=files,
            poi_scope={"mission_id": mission_id, "route_ids": sorted(routes)},
            pois=pois,
        )
