"""Mission-owned transport commands, prepared and published with the planning journal."""

from datetime import datetime, timezone

from app.mission import storage
from app.mission.availability import resolved_leg_availability
from app.mission.availability_context import for_run
from app.mission.availability_models import (
    AvailabilityChange,
    MissionAvailability,
    aware_utc,
)
from app.mission.planning.errors import PlanningFailure
from app.mission.planning.identity import planning_identity
from app.mission.planning.journal import json_bytes, read_scope

RECEIPTS = "transport_availability_commands"


class AvailabilityService:
    def __init__(self, store, *, clock=None, run_service=None, source_mode="live"):
        from app.operator.clock import SystemClock

        self.store = store
        self.clock = clock or SystemClock()
        self.run_service = run_service
        self.source_mode = source_mode

    def _load(self, mission_id):
        # Share the fail-closed recovery contract with all planning readers.
        if any(self.store.journal.directory.glob("*.json")):
            raise PlanningFailure(
                503,
                "planning_recovery_required",
                "Storage recovery is required",
                retryable=True,
            )
        mission = storage.load_mission_v2(mission_id)
        if mission is None:
            raise PlanningFailure(404, "mission_not_found", "Mission not found")
        return mission

    def _context(self, mission):
        active = [leg for leg in mission.legs if leg.is_active]
        leg = active[0] if len(active) == 1 else None
        run_id = None
        reason = (
            None
            if leg
            else "Activate a mission leg before recording a transport action"
        )
        from app.mission.active_context import resolve_active_mission_leg_context

        resolution = resolve_active_mission_leg_context(self.store.route_manager)
        context = resolution.context
        if leg and (
            context is None
            or context.parent_mission_id != mission.id
            or context.leg.id != leg.id
        ):
            reason = "The active mission leg and route must match before recording a transport action"
        mode = self.source_mode() if callable(self.source_mode) else self.source_mode
        runtime = self.run_service() if callable(self.run_service) else self.run_service
        if mode == "simulation":
            status = runtime.status() if runtime else None
            run = (
                status.run
                if status and status.state in ("running", "completed")
                else None
            )
            if (
                run is None
                or leg is None
                or run.mission_id != mission.id
                or run.leg_id != leg.id
            ):
                return (
                    leg,
                    None,
                    None,
                    "An authoritative simulation clock for the active mission leg is required",
                )
            now, run_id = run.simulation_time, run.run_id
        else:
            now = self.clock.now()
        if now is None:
            return leg, run_id, None, "The mission clock is unavailable"
        return leg, run_id, aware_utc(now), reason

    def _view(self, mission):
        leg, run_id, now, reason = self._context(mission)
        selected = for_run(mission, run_id)
        legs = []
        for item in mission.legs:
            snapshot = resolved_leg_availability(selected, item)
            legs.append(
                dict(
                    leg_id=item.id,
                    overrides=item.transports.availability_overrides or {},
                    planned=dict(snapshot.planned),
                    effective=snapshot.resolve(now) if now else None,
                )
            )
        overrides = {
            item.id: item.transports.availability_overrides or {}
            for item in mission.legs
        }
        raw = mission.metadata.get("itinerary_planning")
        if raw:
            from app.mission.planning.models import PlanningManifest
            from app.mission.availability_context import expected_snapshot

            cards = [
                card
                for card in PlanningManifest.model_validate(raw).expected_legs
                if not card.retired
            ]
            managed = {card.installed_leg_id for card in cards if card.installed_leg_id}
            legs = [row for row in legs if row["leg_id"] not in managed]
            for card in cards:
                snapshot = expected_snapshot(mission, card, run_id=run_id)
                partial = card.draft.availability_overrides or {} if card.draft else {}
                overrides[card.id] = partial
                if card.installed_leg_id:
                    overrides[card.installed_leg_id] = partial
                legs.append(
                    dict(
                        leg_id=card.id,
                        installed_leg_id=card.installed_leg_id,
                        overrides=partial,
                        planned=dict(snapshot.planned),
                        effective=snapshot.resolve(now) if now else None,
                    )
                )
        return dict(
            mission_id=mission.id,
            revision=mission.availability.revision,
            defaults=mission.availability.defaults,
            leg_overrides=overrides,
            history=[
                item.model_dump(mode="json") for item in mission.availability.history
            ],
            simulation_run_id=run_id,
            as_of=now,
            active_leg_id=leg.id if leg else None,
            effective=(
                resolved_leg_availability(selected, leg).resolve(now)
                if leg and now
                else None
            ),
            operator_actions_allowed=reason is None,
            operator_actions_unavailable_reason=reason,
            legs=legs,
        )

    def read(self, mission_id):
        with storage.get_active_leg_lock():
            return self._view(self._load(mission_id))

    def _prepare(self, mission, previous, *, run_id=None):
        """Prepare only detached candidate values; no mutable parent reads in calculators."""
        from app.mission import timeline_preparation
        from app.mission.planning.models import PlanningManifest
        from app.mission.planning.inputs import (
            build_inputs,
            canonical_inputs,
            draft_to_mission_leg,
        )
        from app.mission.planning.grid import build_context
        from app.mission.effective_route import prepare_effective_route

        files = {}
        raw = mission.metadata.get("itinerary_planning")
        manifest = PlanningManifest.model_validate(raw) if raw else None
        if manifest:
            manifest.revision += 1
            for card in manifest.expected_legs:
                card.review = None
                if card.draft:
                    card.draft.evaluation_context = None
            for ref in manifest.proposal_refs:
                ref.state = "stale"
            for proposal in manifest.proposals:
                proposal.state = "stale"
        for leg in mission.legs:
            card = (
                next(
                    (
                        c
                        for c in manifest.expected_legs
                        if c.installed_leg_id == leg.id and not c.retired
                    ),
                    None,
                )
                if manifest
                else None
            )
            snapshot = resolved_leg_availability(for_run(mission, run_id), leg)
            if card:
                snapshot = snapshot.model_copy(update={"leg_id": card.id})
            if leg.route_id:
                if leg.transports.planning_policy is not None:
                    if card is not None:
                        # Rebuild the accepted executable plan, never pending card edits.
                        accepted = next(
                            item for item in previous.legs if item.id == leg.id
                        )
                        route = prepare_effective_route(
                            accepted, self.store.route_manager
                        )
                        _, draft, _ = canonical_inputs(accepted, route)
                        draft.availability_overrides = (
                            leg.transports.availability_overrides
                        )
                        from app.mission.planning.models import RouteBinding

                        source = self.store.route_manager.get_route(leg.route_id)
                        bound = card.model_copy(
                            deep=True,
                            update={
                                "route": RouteBinding(
                                    route_id=leg.route_id,
                                    source_id=leg.route_id,
                                    content_hash=source.content_hash,
                                    filename="route.kml",
                                ),
                                "draft": draft,
                                "ar_rows": draft.ar_corrections,
                                "ar_section_status": (
                                    "listed" if draft.ar_corrections else "empty"
                                ),
                            },
                        )
                        inputs = build_inputs(
                            bound,
                            draft,
                            self.store.route_manager,
                            self.store.poi_manager,
                            self.store.planning_constraints_provider(),
                            availability=snapshot,
                        )
                        context = build_context(inputs, draft)
                        projected = draft_to_mission_leg(
                            inputs, draft, context, leg_id=leg.id
                        )
                        projected.transports.initial_ka_satellite_ids = list(
                            leg.transports.initial_ka_satellite_ids
                        )
                        leg.transports = projected.transports
                        leg.adjusted_departure_time = projected.adjusted_departure_time
                    else:
                        route = prepare_effective_route(leg, self.store.route_manager)
                        inputs, _, context = canonical_inputs(
                            leg,
                            route,
                            self.store.planning_constraints_provider(),
                            poi_manager=self.store.poi_manager,
                            availability=snapshot,
                        )
                        leg.transports.planning_inputs = inputs
                        leg.transports.evaluation_context = context
                artifacts = timeline_preparation.prepare_mission_timeline(
                    leg,
                    self.store.route_manager,
                    self.store.poi_manager,
                    parent_mission_id=mission.id,
                    constraint_config=self.store.planning_constraints_provider(),
                    availability=snapshot,
                )
                files[storage.get_leg_timeline_path(leg.id, mission.id).resolve()] = (
                    json_bytes(artifacts.timeline.model_dump(mode="json"))
                )
            files[storage.get_mission_leg_file_path(mission.id, leg.id).resolve()] = (
                json_bytes(leg.model_dump(mode="json"))
            )
        if manifest:
            mission.metadata["itinerary_planning"] = manifest.storage_record()
        files[storage.get_mission_file_path(mission.id).resolve()] = json_bytes(
            mission.model_copy(update={"legs": []}).model_dump(mode="json")
        )
        return files

    def command(self, mission_id, request, *, action=False):
        with storage.get_active_leg_lock(), storage.get_mission_lock(mission_id):
            mission = self._load(mission_id)
            active, run_id, now, reason = (
                self._context(mission) if action else (None, None, None, None)
            )
            identity = planning_identity(
                {
                    "action": action,
                    **request.model_dump(
                        mode="json", exclude={"expected_revision", "command_id"}
                    ),
                }
            )
            receipts = mission.metadata.get(RECEIPTS, [])
            accepted = next(
                (item for item in receipts if item["id"] == request.command_id), None
            )
            if accepted:
                if accepted["identity"] != identity:
                    raise PlanningFailure(
                        409,
                        "availability_command_conflict",
                        "Command ID was used for different input",
                    )
                return self._view(mission)
            if mission.availability.revision != request.expected_revision:
                raise PlanningFailure(
                    409,
                    "availability_revision_conflict",
                    "Availability changed; reload before saving",
                    action="reload",
                )
            candidate = mission.model_copy(deep=True)
            defaults = dict(candidate.availability.defaults)
            history = candidate.availability.history
            if action:
                if reason:
                    raise PlanningFailure(
                        409, "availability_action_unavailable", reason
                    )
                history = (
                    *history,
                    AvailabilityChange(
                        id=request.command_id,
                        transport=request.transport,
                        unavailable=request.action == "unavailable",
                        effective_at=now,
                        reason=request.reason,
                        simulation_run_id=run_id,
                    ),
                )
            else:
                runtime = (
                    self.run_service()
                    if callable(self.run_service)
                    else self.run_service
                )
                if runtime:
                    runtime.assert_plan_edit_allowed(mission_id, None)
                defaults.update(request.defaults or {})
                raw = candidate.metadata.get("itinerary_planning")
                from app.mission.planning.models import PlanningManifest

                manifest = PlanningManifest.model_validate(raw) if raw else None
                for leg_id, overrides in (request.leg_overrides or {}).items():
                    leg = next(
                        (leg for leg in candidate.legs if leg.id == leg_id), None
                    )
                    card = (
                        next(
                            (
                                c
                                for c in manifest.expected_legs
                                if (c.id == leg_id or c.installed_leg_id == leg_id)
                                and not c.retired
                            ),
                            None,
                        )
                        if manifest
                        else None
                    )
                    if leg is None and card is None:
                        raise PlanningFailure(404, "leg_not_found", "Leg not found")
                    if card is not None:
                        if card.draft is None:
                            from app.mission.planning.models import PlanningDraft

                            card.draft = PlanningDraft()
                        card.draft.availability_overrides = overrides
                        leg = next(
                            (
                                leg
                                for leg in candidate.legs
                                if leg.id == card.installed_leg_id
                            ),
                            leg,
                        )
                    if leg is not None:
                        leg.transports.availability_overrides = overrides
                if manifest:
                    candidate.metadata["itinerary_planning"] = manifest.storage_record()
            try:
                candidate.availability = MissionAvailability(
                    revision=mission.availability.revision + 1,
                    defaults=defaults,
                    history=history,
                    simulation_run_id=None,
                )
                candidate.updated_at = datetime.now(timezone.utc)
                candidate.metadata[RECEIPTS] = [
                    *receipts,
                    {"id": request.command_id, "identity": identity},
                ]
                files = self._prepare(candidate, mission, run_id=run_id)
            except ValueError as exc:
                raise PlanningFailure(
                    422, "availability_regeneration_failed", str(exc)
                ) from exc
            # Retain generated identities and applicability for the shared POI consumer.
            scope = {
                "mission_id": mission_id,
                "route_ids": sorted({leg.route_id for leg in candidate.legs}),
            }
            pois = read_scope(self.store.poi_manager.pois_file, scope)
            try:
                self.store.journal.commit(files, poi_scope=scope, pois=pois)
            finally:
                if not any(self.store.journal.directory.glob("*.json")):
                    self.store.poi_manager.reload_pois()
            from app.mission.slide_cache.coordinator import saved_mission

            saved_mission(mission, candidate)
            from app.services.metrics_changes import mission_metrics_changes

            mission_metrics_changes._notify_metrics_changed(
                "transport availability publication"
            )
            return self._view(candidate)
