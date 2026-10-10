"""Revision-CAS persistence for drafts and already validated reviewed artifacts."""

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.mission import storage
from app.models.poi import POI
from app.services.poi.manager import _route_geometry_hash

from .errors import PlanningFailure, conflict
from .identity import planning_identity
from .journal import Journal, json_bytes
from .models import (
    ExpectedLegCard,
    PlanningError,
    PlanningManifest,
    PlanningView,
    ReviewRecord,
)
from .sources import SourceStore


def leg_identity(leg):
    # Review identity must not hash itself or publication bookkeeping.
    return planning_identity(
        leg.model_dump(exclude={"review", "installed_leg_id", "retired"})
    )


def selection_errors(draft):
    if draft is None or not draft.permitted_satellite_ids:
        return [
            PlanningError(
                code="satellite_access_required",
                field="permitted_satellite_ids",
                message="Select permitted X-band satellites and confirm access",
            )
        ]
    confirmation = draft.access_confirmation
    if not confirmation or not confirmation.confirmed:
        return [
            PlanningError(
                code="satellite_access_required",
                field="access_confirmation",
                message="Confirm access to the selected satellites",
            )
        ]
    return []


class PlanningStore:
    def __init__(self, root: Path, route_manager, poi_manager):
        self.root = Path(root).resolve()
        if self.root != storage.MISSIONS_DIR.resolve():
            raise ValueError(
                "Planning and mission storage must share the canonical root"
            )
        self.route_manager = route_manager
        self.poi_manager = poi_manager
        self.sources = SourceStore(self.root, route_manager.routes_dir)
        self.journal = Journal(
            self.root, route_manager.routes_dir, poi_manager.pois_file
        )
        route_manager._profile_resolver = self.sources.resolve_profile

    def recover(self):
        with storage.get_active_leg_lock():
            self.journal.recover()
            self.poi_manager.reload_pois()
            self.sources.cleanup_expired()

    def _load(self, mission_id):
        # Unrecovered interruption must never serve partial state.
        if self.journal.directory.exists() and any(
            self.journal.directory.glob("*.json")
        ):
            raise PlanningFailure(
                503,
                "planning_recovery_required",
                "Planning recovery must complete before reading",
                retryable=True,
            )
        mission = storage.load_mission_v2(mission_id)
        if mission is None:
            raise PlanningFailure(404, "mission_not_found", "Mission not found")
        raw = mission.metadata.get("itinerary_planning")
        if raw is None:
            raise PlanningFailure(
                404, "planning_not_found", "Mission has no itinerary plan"
            )
        return mission, PlanningManifest.model_validate(raw)

    def _view(self, mission, manifest):
        cards = [
            ExpectedLegCard(
                leg=leg,
                input_identity=leg_identity(leg),
                errors=selection_errors(leg.draft),
            )
            for leg in sorted(manifest.expected_legs, key=lambda leg: leg.ordinal)
            if not leg.retired
        ]
        errors = [error for card in cards for error in card.errors]
        return PlanningView(
            mission=storage.public_mission(mission),
            revision=manifest.revision,
            expected_legs=cards,
            errors=errors,
        )

    def read(self, mission_id):
        with storage.get_active_leg_lock():
            return self._view(*self._load(mission_id))

    def checked(self, mission_id, leg_id, revision, identity=None):
        mission, manifest = self._load(mission_id)
        if manifest.revision != revision:
            raise conflict()
        leg = next(
            (
                leg
                for leg in manifest.expected_legs
                if leg.id == leg_id and not leg.retired
            ),
            None,
        )
        if leg is None:
            raise PlanningFailure(404, "leg_not_found", "Expected leg not found")
        if identity is not None and leg_identity(leg) != identity:
            raise conflict("Draft inputs changed; reload before saving")
        # All referenced active legs, including another parent using a route,
        # prevent mutation of an active planning context.
        route_ids = {leg.route.route_id} if leg.route else set()
        for parent in storage.list_mission_metadata_v2():
            loaded = storage.load_mission_v2(parent.id)
            if any(
                item.is_active
                and (
                    item.id == leg.installed_leg_id
                    and parent.id == mission_id
                    or item.route_id in route_ids
                )
                for item in loaded.legs
            ):
                raise conflict("Deactivate the affected leg before editing")
        return mission, manifest, leg

    def persist(self, mission, manifest, *, files=None, poi_scope=None, pois=None):
        manifest = PlanningManifest.model_validate(manifest.storage_record())
        updated = mission.model_copy(deep=True)
        updated.metadata["itinerary_planning"] = manifest.storage_record()
        updated.updated_at = datetime.now(timezone.utc)
        updated = storage._ordered_mission(updated)
        writes = {
            storage.get_mission_file_path(mission.id).resolve(): json_bytes(
                updated.model_copy(update={"legs": []}).model_dump(mode="json")
            )
        }
        writes.update(files or {})
        try:
            self.journal.commit(writes, poi_scope=poi_scope, pois=pois)
        finally:
            if poi_scope is not None and not any(self.journal.directory.glob("*.json")):
                self.poi_manager.reload_pois()
        return self._view(updated, manifest)

    def save_draft(self, mission_id, leg_id, request):
        with storage.get_active_leg_lock(), storage.get_mission_lock(mission_id):
            mission, manifest, leg = self.checked(
                mission_id, leg_id, request.expected_revision
            )
            leg.draft = request.draft.model_copy(deep=True)
            leg.review = None
            manifest.proposals = [
                p.model_copy(update={"state": "stale"}) for p in manifest.proposals
            ]
            manifest.revision += 1
            return self.persist(mission, manifest)

    def commit_reviewed(self, mission_id, leg_id, request, artifacts):
        """Publish supplied validated results. Task 7 owns evaluation/validation."""
        installed = artifacts.validated_leg
        if installed is None:
            raise PlanningFailure(
                422, "validated_leg_required", "Validated executable leg is required"
            )
        installed = installed.model_copy(deep=True)
        # Build POI values outside persistence locks; no projection/evaluation here.
        records = {}
        geometry_hash = (
            _route_geometry_hash(artifacts.route)
            if any(
                poi._route_segment_index is not None for poi in artifacts.generated_pois
            )
            else None
        )
        for value in artifacts.generated_pois:
            poi = POI(
                id=str(uuid4()),
                **value.model_dump(),
                generated_source="mission-timeline",
                planned_route_segment_index=value._route_segment_index,
                planned_route_geometry_hash=geometry_hash,
            )
            record = poi.model_dump(mode="json")
            record["generated_source"] = "mission-timeline"
            record["planned_route_segment_index"] = poi.planned_route_segment_index
            record["planned_route_geometry_hash"] = poi.planned_route_geometry_hash
            records[poi.id] = record
        with storage.get_active_leg_lock(), storage.get_mission_lock(mission_id):
            mission, manifest, leg = self.checked(
                mission_id, leg_id, request.expected_revision, request.input_identity
            )
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
                    "Validated artifacts do not match the selected inactive leg",
                )
            source = next(
                (s for s in manifest.source_revisions if s.id == leg.route.source_id),
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
            self.sources.resolve_profile(installed.route_id)
            if any(
                p["mission_id"] != mission_id or p["route_id"] != installed.route_id
                for p in records.values()
            ):
                raise PlanningFailure(
                    422,
                    "poi_owner_mismatch",
                    "Prepared markers are outside the selected mission/route",
                )
            if leg.installed_leg_id is None and any(
                item.id == installed.id for item in mission.legs
            ):
                raise conflict("Executable leg ID is already installed")
            scope_routes = {installed.route_id}
            scope_routes.update(
                item.route_id for item in mission.legs if item.id == installed.id
            )
            if any(
                item.id != installed.id and item.route_id in scope_routes
                for item in mission.legs
            ):
                raise conflict(
                    "Managed generated marker scopes cannot be shared by installed legs"
                )
            leg.installed_leg_id = installed.id
            leg.review = ReviewRecord(
                **request.model_dump(exclude={"expected_revision"}),
                saved_at=datetime.now(timezone.utc),
            )
            manifest.review_records.append(leg.review)
            manifest.revision += 1
            mission.legs = [
                item for item in mission.legs if item.id != installed.id
            ] + [installed]
            files = {
                storage.get_mission_leg_file_path(
                    mission_id, installed.id
                ).resolve(): json_bytes(installed.model_dump(mode="json")),
                storage.get_leg_timeline_path(
                    installed.id, mission_id
                ).resolve(): json_bytes(artifacts.timeline.model_dump(mode="json")),
            }
            return self.persist(
                mission,
                manifest,
                files=files,
                poi_scope={"mission_id": mission_id, "route_ids": sorted(scope_routes)},
                pois=records,
            )
