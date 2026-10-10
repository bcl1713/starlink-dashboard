"""Parse outside locks; accept immutable sources with revision-CAS transactions."""

import hashlib
from uuid import uuid4

from app.mission import storage
from app.mission.models import Mission
from app.satellites.catalog import get_satellite_catalog
from app.services.kml_parser import parse_kml_file

from .deadlines import run_bounded
from .errors import PlanningFailure, conflict
from .extract import extract_itinerary
from .identity import planning_identity
from .journal import json_bytes
from .match import ar_match_candidates, match_ar_windows
from .models import (
    PlanningDraft,
    PlanningError,
    PlanningManifest,
    PlanningSatelliteOptions,
    RouteBinding,
    RouteBindingPreview,
)


def _parse_route(path):
    return parse_kml_file(path, profile="planning_v1")


class PlanningService:
    def __init__(self, store):
        self.store = store
        self.sources = store.sources

    @property
    def proposals(self):
        from .proposals import ProposalService

        return ProposalService(self.store)

    def preview(self, mission_id, leg_id, request):
        from .review import preview

        return preview(self, mission_id, leg_id, request)

    def save_reviewed(self, mission_id, leg_id, request):
        from .review import save_reviewed

        return save_reviewed(self, mission_id, leg_id, request)

    def update_managed_leg(self, mission_id, leg_id, updated_leg, revision, identity):
        from .legacy import update_leg

        return update_leg(self, mission_id, leg_id, updated_leg, revision, identity)

    def satellite_options(self):
        from .satellites import satellite_options

        return PlanningSatelliteOptions(
            satellites=satellite_options(
                self.store.poi_manager, get_satellite_catalog(read_only=True)
            )
        )

    def validate_selection(self, selection):
        eligible = {
            sat.id for sat in self.satellite_options().satellites if sat.eligible
        }
        if set(selection.permitted_satellite_ids) - eligible:
            raise PlanningFailure(
                422,
                "invalid_satellite_selection",
                "Selected satellites must be eligible configured X-band satellites",
            )

    def preview_itinerary(self, data, filename):
        source = self.sources.stage(data, "pdf", None, filename)
        try:
            preview = extract_itinerary(data).model_copy(
                update={
                    "preview_id": source.id,
                    "source": source,
                    "expires_at": source.expires_at,
                }
            )
            self.sources.save_preview(
                source.id,
                {
                    "kind": "itinerary",
                    "preview": preview.model_dump(mode="json"),
                    "source": source.storage_record(),
                },
            )
            return preview
        except BaseException:
            self.sources.discard(source)
            raise

    def create(self, request):
        self.validate_selection(request)
        key = hashlib.sha256(request.idempotency_key.encode()).hexdigest()
        identity = planning_identity(request.model_dump(exclude={"idempotency_key"}))
        idempotency_path = self.sources.root / "idempotency" / f"{key}.json"
        with storage.get_active_leg_lock():
            if idempotency_path.exists():
                import json

                record = json.loads(idempotency_path.read_bytes())
                if record["identity"] != identity:
                    raise conflict("Idempotency key already used for different input")
                return self.store.read(record["mission_id"])
            record, source, data = self.sources.acceptance_snapshot(request.preview_id)
        if record["kind"] != "itinerary":
            raise PlanningFailure(
                422, "wrong_preview_kind", "An itinerary preview is required"
            )
        if not request.itinerary.expected_legs:
            raise PlanningFailure(
                422, "expected_legs_required", "At least one expected leg is required"
            )
        mission_id = str(uuid4())
        accepted, files = self.sources.acceptance_files(source, mission_id, data)
        draft = PlanningDraft(
            **request.model_dump(
                include={
                    "permitted_satellite_ids",
                    "access_confirmation",
                    "starshield_enabled",
                }
            )
        )
        legs = []
        for original in request.itinerary.expected_legs:
            if (
                original.route
                or original.installed_leg_id
                or original.review
                or original.retired
            ):
                raise PlanningFailure(
                    422,
                    "invalid_expected_leg",
                    "Imported cards cannot supply server-owned bindings or reviews",
                )
            leg_draft = draft.model_copy(deep=True)
            if original.draft and original.draft.no_ars_confirmed:
                if original.ar_section_status == "unrecognized" or any(
                    row.match_status != "excluded" for row in original.ar_rows
                ):
                    raise PlanningFailure(
                        422,
                        "invalid_no_ar_confirmation",
                        "Correct the AR section and active rows before confirming no ARs",
                    )
                leg_draft.no_ars_confirmed = True
            legs.append(original.model_copy(update={"draft": leg_draft}))
        from .models import ItineraryData

        baseline = (
            ItineraryData.model_validate(record["preview"]["parsed_values"])
            if record.get("preview", {}).get("parsed_values")
            else None
        )
        manifest = PlanningManifest(
            source_revisions=[accepted], expected_legs=legs, itinerary_baseline=baseline
        )
        mission = Mission(
            id=mission_id,
            name=request.itinerary.name,
            metadata={
                "itinerary": request.itinerary.model_dump(
                    mode="json", exclude={"expected_legs"}
                )
            },
        )
        files[idempotency_path] = json_bytes(
            {"identity": identity, "mission_id": mission_id}
        )
        with storage.get_active_leg_lock(), storage.get_mission_lock(mission_id):
            if idempotency_path.exists():
                import json

                previous = json.loads(idempotency_path.read_bytes())
                if previous["identity"] != identity:
                    raise conflict("Idempotency key already used for different input")
                return self.store.read(previous["mission_id"])
            self.sources.get_preview(request.preview_id)
            return self.store.persist(mission, manifest, files=files)

    def preview_route(self, mission_id, leg_id, data, revision, filename="route.kml"):
        with storage.get_active_leg_lock():
            _, _, leg = self.store.checked(mission_id, leg_id, revision)
            leg = leg.model_copy(deep=True)
        source = self.sources.stage(data, "kml", mission_id, filename)
        try:
            route = run_bounded(_parse_route, (self.sources.path(source),), 10)
            binding = RouteBinding(
                route_id=source.id,
                source_id=source.id,
                content_hash=source.content_hash,
                filename=source.filename,
            )
            errors = []
            timing = route.timing_profile
            if (
                timing is None
                or timing.departure_time is None
                or timing.arrival_time is None
            ):
                raise PlanningFailure(
                    422,
                    "route_timing_required",
                    "KML requires named departure/arrival airports and timed primary route endpoints",
                    action="replace_route",
                )
            if (
                timing.departure_time != leg.departure_time
                or timing.arrival_time != leg.arrival_time
            ):
                errors.append(
                    PlanningError(
                        code="route_time_discrepancy",
                        field="route",
                        message="KML and itinerary UTC windows differ",
                    )
                )
            primary = [
                waypoint for waypoint in route.waypoints if waypoint.role != "alternate"
            ]
            if primary and (
                primary[0].name != leg.departure_airport
                or primary[-1].name != leg.arrival_airport
            ):
                errors.append(
                    PlanningError(
                        code="route_endpoint_discrepancy",
                        field="route",
                        message="KML and itinerary endpoints differ",
                    )
                )
            preview = RouteBindingPreview(
                old_source_hash=leg.route.content_hash if leg.route else None,
                unresolved_lock_ids=[
                    lock.id
                    for lock in (leg.draft.locks if leg.draft else [])
                    if lock.anchor
                ],
                unresolved_ar_ids=[
                    row.id
                    for row in (leg.draft.ar_corrections if leg.draft else [])
                    if row.start_anchor or row.end_anchor
                ],
                adjusted_departure_time=(
                    leg.draft.adjusted_departure_time if leg.draft else None
                ),
                preview_id=source.id,
                expected_revision=revision,
                binding=binding,
                discrepancy_errors=errors,
                matched_ar_candidates=ar_match_candidates(leg, route),
                expires_at=source.expires_at,
            )
            matched = match_ar_windows(leg, route)
            self.sources.save_preview(
                source.id,
                {
                    "kind": "route",
                    "mission_id": mission_id,
                    "leg_id": leg_id,
                    "preview": preview.model_dump(mode="json"),
                    "source": source.storage_record(),
                    "matched_ar": [row.model_dump(mode="json") for row in matched],
                    "route": route.model_dump(mode="json"),
                },
            )
            return preview
        except BaseException:
            self.sources.discard(source)
            raise

    def accept_route(self, mission_id, leg_id, request):
        record, source, data = self.sources.acceptance_snapshot(request.preview_id)
        if (
            record.get("kind") != "route"
            or record.get("mission_id") != mission_id
            or record.get("leg_id") != leg_id
            or source.owner != mission_id
        ):
            raise PlanningFailure(
                422,
                "route_preview_owner_mismatch",
                "Preview belongs to another selected leg",
            )
        preview = RouteBindingPreview.model_validate(record["preview"])
        if preview.expected_revision != request.expected_revision:
            raise conflict()
        if {e.code for e in preview.discrepancy_errors} - set(
            request.discrepancy_acknowledgments
        ):
            raise PlanningFailure(
                422,
                "discrepancy_acknowledgment_required",
                "Acknowledge route discrepancies before acceptance",
            )
        accepted, files = self.sources.acceptance_files(source, mission_id, data)
        from app.models.route import ParsedRoute

        route = ParsedRoute.model_validate(record["route"])
        route.metadata.file_path = str(self.sources.routes_dir / f"{source.id}.kml")
        with storage.get_active_leg_lock(), storage.get_mission_lock(mission_id):
            mission, manifest, leg = self.store.checked(
                mission_id, leg_id, request.expected_revision
            )
            self.sources.get_preview(request.preview_id)
            from .store import leg_identity

            previous_identity = leg_identity(leg)
            if leg.route:
                from .revisions import archive_leg

                archive_leg(self.store, mission, manifest, leg, "route_replacement")
                manifest.route_history.append(leg.route)
            leg.route = preview.binding
            leg.review = None
            # Existing corrections and locks survive replacements, including unresolved anchors.
            if leg.draft is None:
                leg.draft = PlanningDraft()
            leg.draft.evaluation_context = None
            if not leg.draft.ar_corrections:
                from .models import ItineraryAR

                leg.draft.ar_corrections = [
                    ItineraryAR.model_validate(row) for row in record["matched_ar"]
                ]
            for reference in manifest.proposal_refs:
                if reference.leg_id == leg.id:
                    reference.state = "stale"
            manifest.source_revisions.append(accepted)
            manifest.route_bindings.append(preview.binding)
            manifest.proposals = [
                (
                    p.model_copy(update={"state": "stale"})
                    if p.input_identity == previous_identity
                    else p
                )
                for p in manifest.proposals
            ]
            manifest.revision += 1
            view = self.store.persist(mission, manifest, files=files)
            self.store.route_manager.add_route(source.id, route)
            return view

    def preview_revision(self, mission_id, data, revision, filename="itinerary.pdf"):
        from .revisions import mission_metadata, preview_revision

        with storage.get_active_leg_lock():
            mission, manifest = self.store._load(mission_id)
            if manifest.revision != revision:
                raise conflict()
        source = self.sources.stage(data, "pdf", mission_id, filename)
        try:
            incoming = extract_itinerary(data).model_copy(
                update={
                    "preview_id": source.id,
                    "source": source,
                    "expires_at": source.expires_at,
                }
            )
            preview = preview_revision(manifest, incoming, mission_metadata(mission))
            self.sources.save_preview(
                source.id,
                {
                    "kind": "revision",
                    "mission_id": mission_id,
                    "preview": preview.model_dump(mode="json"),
                    "source": source.storage_record(),
                },
            )
            return preview
        except BaseException:
            self.sources.discard(source)
            raise

    def apply_revision(self, mission_id, request):
        from .models import RevisionPreview
        from .revisions import reconcile, revision_identity

        record, source, _ = self.sources.acceptance_snapshot(request.preview_id)
        if (
            record.get("kind") != "revision"
            or record.get("mission_id") != mission_id
            or source.owner != mission_id
        ):
            raise PlanningFailure(
                422, "revision_owner_mismatch", "Revision belongs to another mission"
            )
        preview = RevisionPreview.model_validate(
            {**record["preview"], "source": source}
        )
        with storage.get_active_leg_lock():
            mission, current = self.store._load(mission_id)
            if (
                current.revision != request.expected_revision
                or preview.expected_revision != request.expected_revision
                or revision_identity(current) != request.input_identity
                or preview.input_identity != request.input_identity
            ):
                raise conflict()
        if preview.lower_revision and not request.allow_lower_revision:
            raise PlanningFailure(
                422,
                "lower_source_revision",
                "Explicitly authorize the lower source revision",
            )
        if preview.identical_content:
            with storage.get_active_leg_lock():
                mission, latest = self.store._load(mission_id)
                if (
                    latest.revision != request.expected_revision
                    or revision_identity(latest) != request.input_identity
                ):
                    raise conflict()
                return self.store._view(mission, latest)
        revised = reconcile(current, preview, request)
        return self.store.commit_revision(mission_id, request, revised)

    def retire_managed_leg(self, mission_id, installed_id, revision, identity):
        from .models import ApplyRevision
        from .revisions import revision_identity

        if revision is None or identity is None:
            raise conflict("Reload planning before deleting a managed leg")
        with storage.get_active_leg_lock():
            _, manifest = self.store._load(mission_id)
            card = next(
                (
                    x
                    for x in manifest.expected_legs
                    if x.installed_leg_id == installed_id and not x.retired
                ),
                None,
            )
            if card is None:
                raise PlanningFailure(404, "leg_not_found", "Managed leg not found")
            self.store.checked(mission_id, card.id, revision, identity)
            revised = manifest.model_copy(deep=True)
            for item in revised.expected_legs:
                if item.id == card.id:
                    item.retired = True
                    item.installed_leg_id = None
            for index, item in enumerate(
                sorted(
                    (x for x in revised.expected_legs if not x.retired),
                    key=lambda x: x.ordinal,
                ),
                1,
            ):
                item.ordinal = index
            request = ApplyRevision(
                preview_id="retirement",
                expected_revision=revision,
                input_identity=revision_identity(manifest),
                leg_mappings=[],
            )
        return self.store.commit_revision(mission_id, request, revised, retirement=True)
