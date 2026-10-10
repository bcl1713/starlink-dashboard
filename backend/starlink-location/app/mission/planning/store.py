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
    errors = []
    if draft.unresolved_aar_windows:
        errors.append(
            PlanningError(
                code="unresolved_aar_windows",
                field="unresolved_aar_windows",
                message="Resolve pending legacy AR windows using accepted timed endpoints",
            )
        )
    if draft.unresolved_x_transitions:
        errors.append(
            PlanningError(
                code="unresolved_x_transitions",
                field="unresolved_x_transitions",
                message="Choose an accepted timed route occurrence or remove each unresolved legacy swap",
            )
        )
    if not confirmation or not confirmation.confirmed:
        errors.append(
            PlanningError(
                code="satellite_access_required",
                field="access_confirmation",
                message="Confirm access to the selected satellites",
            )
        )
    permitted = set(draft.permitted_satellite_ids)
    for field, selected in [
        ("initial_x_satellite_id", draft.initial_x_satellite_id),
        *(
            (f"swaps.{i}.target_satellite_id", swap.target_satellite_id)
            for i, swap in enumerate(draft.swaps)
        ),
        *(
            (f"locks.{i}.target_satellite_id", lock.target_satellite_id)
            for i, lock in enumerate(draft.locks)
        ),
    ]:
        if selected is not None and selected not in permitted:
            errors.append(
                PlanningError(
                    code="satellite_not_permitted",
                    field=field,
                    message="Assignment is outside the permitted satellite set",
                )
            )
    return errors


class PlanningStore:
    def __init__(self, root: Path, route_manager, poi_manager):
        self.root = Path(root).resolve()
        if self.root != storage.MISSIONS_DIR.resolve():
            raise ValueError(
                "Planning and mission storage must share the canonical root"
            )
        from app.satellites.rules import ConstraintConfig

        self.planning_constraints_provider = ConstraintConfig
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
                leg=leg.model_copy(deep=True),
                input_identity=leg_identity(leg),
                errors=selection_errors(leg.draft),
            )
            for leg in sorted(manifest.expected_legs, key=lambda leg: leg.ordinal)
            if not leg.retired
        ]
        from .proposals import ProposalService

        proposals = ProposalService(self)
        from .service import PlanningService

        eligible = {
            s.id
            for s in PlanningService(self).satellite_options().satellites
            if s.eligible
        }
        for card in cards:
            if card.leg.review:
                from .proposals import environment_identity

                try:
                    current = environment_identity(
                        self, card.leg, self.planning_constraints_provider()
                    )
                except (ValueError, PlanningFailure):
                    current = None
                if current is None or current != card.leg.review.environment_identity:
                    card.leg.review = None
                    card.errors.append(
                        PlanningError(
                            code="review_dependencies_changed",
                            message="Planning dependencies changed; preview and review again",
                        )
                    )
            if (
                card.leg.draft
                and set(card.leg.draft.permitted_satellite_ids) - eligible
            ):
                card.errors.append(
                    PlanningError(
                        code="invalid_satellite_selection",
                        field="permitted_satellite_ids",
                        message="A selected satellite is no longer eligible in the current catalog",
                    )
                )
            references = [
                ref for ref in manifest.proposal_refs if ref.leg_id == card.leg.id
            ]
            if references:
                card.computation_status = proposals.status(
                    card.leg, references[-1], manifest.revision
                )
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

    def checked(
        self, mission_id, leg_id, revision, identity=None, *, allow_active=False
    ):
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
        for parent in ([] if allow_active else storage.list_mission_metadata_v2()):
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
        validated_context = None
        if request.draft.evaluation_context is not None:

            from .grid import swap_times, validate_context
            from .inputs import build_inputs

            with storage.get_active_leg_lock():
                _, _, source_leg = self.checked(
                    mission_id, leg_id, request.expected_revision
                )
                source_leg = source_leg.model_copy(deep=True)
            # Accept a new client-supplied context only after validating all
            # captured inputs and exact current seeds outside commit locks.
            try:
                inputs = build_inputs(
                    source_leg,
                    request.draft,
                    self.route_manager,
                    self.poi_manager,
                    self.planning_constraints_provider(),
                )
                validate_context(
                    inputs, request.draft, request.draft.evaluation_context
                )
                if request.draft.evaluation_context.seed_times == sorted(
                    set(swap_times(inputs, request.draft))
                ):
                    validated_context = request.draft.evaluation_context.model_copy(
                        deep=True
                    )
            except ValueError:
                pass
        with storage.get_active_leg_lock(), storage.get_mission_lock(mission_id):
            mission, manifest, leg = self.checked(
                mission_id, leg_id, request.expected_revision
            )
            from .inputs import structural_draft

            previous = leg.draft
            incoming = request.draft.model_copy(deep=True)
            # Context is server-owned. Explicit manual timing edits always reseed,
            # including moving a swap onto an already existing candidate instant.
            unchanged = previous is not None and structural_draft(
                previous
            ) == structural_draft(incoming)
            timing = lambda d: [(s.id, s.anchor.model_dump()) for s in d.swaps]
            same_timing = previous is not None and timing(previous) == timing(incoming)
            incoming.evaluation_context = (
                previous.evaluation_context
                if unchanged and same_timing and previous.evaluation_context is not None
                else validated_context
            )
            if previous is not None and set(previous.permitted_satellite_ids) != set(
                incoming.permitted_satellite_ids
            ):
                incoming.access_confirmation = None
            leg.draft = incoming
            for reference in manifest.proposal_refs:
                reference.state = "stale"
            if request.ar_section_status is not None:
                leg.ar_section_status = request.ar_section_status
            rows = leg.draft.ar_corrections or leg.ar_rows
            if leg.ar_section_status == "unrecognized" or any(
                row.match_status != "excluded" for row in rows
            ):
                leg.draft.no_ars_confirmed = False
            leg.review = None
            manifest.proposals = [
                p.model_copy(update={"state": "stale"}) for p in manifest.proposals
            ]
            manifest.revision += 1
            return self.persist(mission, manifest)

    def commit_reviewed(
        self, mission_id, leg_id, request, artifacts, *, validate=None, environment=None
    ):
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
            if validate is not None:
                validate(leg)
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
                **request.model_dump(exclude={"expected_revision", "idempotency_key"}),
                saved_at=datetime.now(timezone.utc),
                environment_identity=environment,
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

    def commit_revision(self, mission_id, request, revised, *, retirement=False):
        from .proposals import environment_identity
        from .revisions import (
            archive_leg,
            merge_metadata,
            mission_metadata,
            revision_identity,
        )

        files = {}
        if not retirement:
            _, source, data = self.sources.acceptance_snapshot(request.preview_id)
            accepted, files = self.sources.acceptance_files(source, mission_id, data)
        with storage.get_active_leg_lock(), storage.get_mission_lock(mission_id):
            mission, current = self._load(mission_id)
            if (
                current.revision != request.expected_revision
                or revision_identity(current) != request.input_identity
            ):
                raise conflict()
            if not retirement:
                self.sources.get_preview(request.preview_id)
            changed = set()
            retired_ids = set()
            routes = set()
            # Rebase server-owned derived payload indexes acquired after preview.
            revised.proposals = current.proposals
            revised.proposal_refs = current.proposal_refs
            revised.review_records = current.review_records
            revised.leg_history = current.leg_history
            for old in current.expected_legs:
                if old.retired:
                    continue
                new = next((x for x in revised.expected_legs if x.id == old.id), None)
                if new is None:
                    raise PlanningFailure(
                        422,
                        "invalid_revision",
                        "Existing leg must be retained or archived",
                    )
                if new == old:
                    continue
                self.checked(mission_id, old.id, request.expected_revision)
                archive_leg(
                    self,
                    mission,
                    revised,
                    old,
                    "retirement" if new.retired else "revision",
                )
                if new.retired:
                    retired_ids.add(old.installed_leg_id)
                    if old.installed_leg_id:
                        installed = next(
                            (x for x in mission.legs if x.id == old.installed_leg_id),
                            None,
                        )
                        if installed:
                            routes.add(installed.route_id)
                        files[
                            storage.get_mission_leg_file_path(
                                mission_id, old.installed_leg_id
                            ).resolve()
                        ] = None
                        files[
                            storage.get_leg_timeline_path(
                                old.installed_leg_id, mission_id
                            ).resolve()
                        ] = None
                    changed.add(old.id)
                    continue
                pure_reorder = old.model_dump(
                    exclude={"ordinal", "review"}
                ) == new.model_dump(exclude={"ordinal", "review"})
                if (
                    pure_reorder
                    and old.review
                    and old.review.input_identity == leg_identity(old)
                ):
                    try:
                        unchanged_environment = (
                            old.review.environment_identity
                            == environment_identity(
                                self, old, self.planning_constraints_provider()
                            )
                        )
                    except (PlanningFailure, ValueError):
                        unchanged_environment = False
                    if unchanged_environment:
                        new.review = old.review.model_copy(
                            update={"input_identity": leg_identity(new)}
                        )
                    else:
                        new.review = None
                elif not pure_reorder:
                    changed.add(old.id)
                    new.review = None
                    if new.draft:
                        new.draft.evaluation_context = None
            if any(
                item.id not in retired_ids and item.route_id in routes
                for item in mission.legs
            ):
                raise conflict(
                    "Managed marker scopes cannot be shared by installed legs"
                )
            mission.legs = [x for x in mission.legs if x.id not in retired_ids]
            for ref in revised.proposal_refs:
                if ref.leg_id in changed:
                    ref.state = "stale"
            for proposal in revised.proposals:
                if any(
                    proposal.input_identity == leg_identity(x)
                    for x in current.expected_legs
                    if x.id in changed
                ):
                    proposal.state = "stale"
            if not retirement:
                revised.source_revisions.append(accepted)
                metadata = request.itinerary or revised.itinerary_baseline
                if metadata:
                    merged = merge_metadata(
                        current.itinerary_baseline,
                        mission_metadata(mission),
                        metadata,
                        request.correction_resolutions,
                    )
                    mission.name = merged.name
                    mission.metadata["itinerary"] = {
                        **mission.metadata.get("itinerary", {}),
                        **merged.model_dump(mode="json"),
                    }
            revised.revision = current.revision + 1
            return self.persist(
                mission,
                revised,
                files=files,
                poi_scope=(
                    {"mission_id": mission_id, "route_ids": sorted(routes)}
                    if routes
                    else None
                ),
                pois={},
            )
