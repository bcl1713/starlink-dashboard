"""Parse each upload once, then bind an explicitly assigned batch in one journal."""

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from app.mission import storage
from app.models.route import ParsedRoute
from app.services.kml_parser import KMLParseError

from .deadlines import PlanningDeadlineError, PlanningWorkerError, run_bounded
from .errors import PlanningFailure, conflict
from .match import match_ar_windows
from .models import (
    BatchRouteAttachment,
    BatchRouteCandidate,
    BatchRoutePreview,
    PlanningDraft,
    PlanningError,
    RouteBinding,
)
from .revisions import archive_leg
from .service import _parse_route
from .store import leg_identity

MAX_BATCH_FILES = 16
MAX_BATCH_BYTES = 40 * 1024 * 1024


def candidates(leg, route):
    timing = route.timing_profile
    primary = [point for point in route.waypoints if point.role != "alternate"]
    airports = bool(primary) and (primary[0].name, primary[-1].name) == (
        leg.departure_airport,
        leg.arrival_airport,
    )
    times = (timing.departure_time, timing.arrival_time) == (
        leg.departure_time,
        leg.arrival_time,
    )
    errors, reasons = [], []
    for matches, reason, code, message in [
        (
            airports,
            "airports_match",
            "route_endpoint_discrepancy",
            "KML and itinerary endpoints differ",
        ),
        (
            times,
            "utc_window_matches",
            "route_time_discrepancy",
            "KML and itinerary UTC windows differ",
        ),
    ]:
        if matches:
            reasons.append(reason)
        else:
            errors.append(PlanningError(code=code, field="route", message=message))
    return BatchRouteCandidate(
        leg_id=leg.id, reasons=reasons, discrepancy_errors=errors
    )


def preview_routes(service, mission_id, files, expected_revision):
    if (
        not files
        or len(files) > MAX_BATCH_FILES
        or sum(len(data) for _, data in files) > MAX_BATCH_BYTES
        or any(len(data) > 10 * 1024 * 1024 for _, data in files)
    ):
        raise PlanningFailure(
            422,
            "route_batch_limit",
            "Choose 1–16 KMLs, at most 10 MiB each and 40 MiB total",
        )
    with storage.get_active_leg_lock():
        _, manifest = service.store._load(mission_id)
        if manifest.revision != expected_revision:
            raise conflict()
        legs = [
            leg.model_copy(deep=True)
            for leg in manifest.expected_legs
            if not leg.retired
        ]
    attachments, staged, records, seen = [], [], {}, set()
    try:
        for filename, data in files:
            digest = hashlib.sha256(data).hexdigest()
            attachment = BatchRouteAttachment(
                attachment_id=str(uuid4()),
                filename=Path(filename).name,
                content_hash=digest,
            )
            attachments.append(attachment)
            if digest in seen:
                attachment.errors.append(
                    PlanningError(
                        code="duplicate_route_upload",
                        message="Duplicate KML content; keep one attachment",
                    )
                )
                continue
            seen.add(digest)
            source = service.sources.stage(data, "kml", mission_id, filename)
            staged.append(source)
            attachment.attachment_id = source.id
            try:
                route = run_bounded(_parse_route, (service.sources.path(source),), 10)
                if (
                    route.timing_profile is None
                    or not route.timing_profile.departure_time
                    or not route.timing_profile.arrival_time
                ):
                    raise PlanningFailure(
                        422,
                        "route_timing_required",
                        "KML requires timed primary route endpoints",
                    )
            except (
                KMLParseError,
                ValueError,
                PlanningFailure,
                PlanningDeadlineError,
                PlanningWorkerError,
            ) as exc:
                attachment.errors.append(
                    PlanningError(
                        code=getattr(exc, "code", "invalid_route_upload"),
                        message="KML cannot be parsed as a timed planning route; replace this attachment",
                        retryable=getattr(exc, "retryable", False),
                    )
                )
                service.sources.discard(source)
                staged.remove(source)
                continue
            primary = [point for point in route.waypoints if point.role != "alternate"]
            attachment.departure_airport = primary[0].name if primary else None
            attachment.arrival_airport = primary[-1].name if primary else None
            attachment.source_departure_time = route.timing_profile.departure_time
            attachment.source_arrival_time = route.timing_profile.arrival_time
            attachment.candidates = [candidates(leg, route) for leg in legs]
            best = max(
                (len(candidate.reasons) for candidate in attachment.candidates),
                default=0,
            )
            suggested = [
                candidate.leg_id
                for candidate in attachment.candidates
                if len(candidate.reasons) == best and best > 0
            ]
            attachment.suggested_leg_id = suggested[0] if len(suggested) == 1 else None
            records[source.id] = {
                "source": source.storage_record(),
                "route": route.model_dump(mode="json"),
            }
        preview = BatchRoutePreview(
            preview_id=staged[0].id if staged else str(uuid4()),
            expected_revision=expected_revision,
            attachments=attachments,
            expires_at=min(
                (s.expires_at for s in staged),
                default=datetime.now(timezone.utc) + timedelta(hours=24),
            ),
        )
        for source in staged:
            service.sources.save_preview(
                source.id,
                {
                    "kind": "route_batch_attachment",
                    "mission_id": mission_id,
                    "batch_id": preview.preview_id,
                    **records[source.id],
                },
            )
        if staged:
            service.sources.save_preview(
                preview.preview_id,
                {
                    "kind": "route_batch",
                    "mission_id": mission_id,
                    "source": staged[0].storage_record(),
                    "preview": preview.model_dump(mode="json"),
                    "records": records,
                },
            )
        return preview
    except BaseException:
        for source in staged:
            service.sources.discard(source)
        raise


def _batch(service, mission_id, preview_id):
    record, source = service.sources.get_preview(preview_id)
    if (
        record.get("kind") != "route_batch"
        or record.get("mission_id") != mission_id
        or source.owner != mission_id
    ):
        raise PlanningFailure(
            422,
            "route_preview_owner_mismatch",
            "Route batch belongs to another mission",
        )
    return record, BatchRoutePreview.model_validate(record["preview"])


def accept_routes(service, mission_id, request):
    with storage.get_active_leg_lock():
        record, preview = _batch(service, mission_id, request.preview_id)
        if request.expected_revision != preview.expected_revision:
            raise conflict()
        if (
            not request.assignments
            or len({a.attachment_id for a in request.assignments})
            != len(request.assignments)
            or len({a.leg_id for a in request.assignments}) != len(request.assignments)
        ):
            raise PlanningFailure(
                422,
                "route_batch_assignments_required",
                "Choose distinct attachments and one route for each selected leg",
            )
        planned = []
        for assignment in request.assignments:
            attachment = next(
                (
                    a
                    for a in preview.attachments
                    if a.attachment_id == assignment.attachment_id
                ),
                None,
            )
            candidate = (
                next(
                    (c for c in attachment.candidates if c.leg_id == assignment.leg_id),
                    None,
                )
                if attachment
                else None
            )
            if attachment is None or attachment.errors or candidate is None:
                raise PlanningFailure(
                    422,
                    "invalid_route_assignment",
                    "Resolve invalid or unmatched attachments before accepting",
                )
            if {e.code for e in candidate.discrepancy_errors} != set(
                assignment.discrepancy_acknowledgments
            ):
                raise PlanningFailure(
                    422,
                    "discrepancy_acknowledgment_required",
                    "Acknowledge each selected route discrepancy",
                )
            _, source, data = service.sources.acceptance_snapshot(
                attachment.attachment_id
            )
            if (
                source.owner != mission_id
                or source.owned_relative_path != f"staging/{source.id}.kml"
                or source.kind != "route_kml"
                or source.content_hash != attachment.content_hash
                or record["records"][source.id]["source"] != source.storage_record()
            ):
                raise conflict("Route batch source changed")
            _, _, leg = service.store.checked(
                mission_id, assignment.leg_id, request.expected_revision
            )
            planned.append(
                (
                    assignment,
                    source,
                    data,
                    record["records"][source.id]["route"],
                    leg.model_copy(deep=True),
                )
            )
    prepared = []
    for assignment, source, data, raw_route, leg in planned:
        accepted, files = service.sources.acceptance_files(source, mission_id, data)
        route = ParsedRoute.model_validate(raw_route)
        route.metadata.file_path = str(service.sources.routes_dir / f"{source.id}.kml")
        matched = match_ar_windows(leg, route)
        prepared.append((assignment, source, accepted, files, route, matched))
    with storage.get_active_leg_lock(), storage.get_mission_lock(mission_id):
        current, _ = _batch(service, mission_id, request.preview_id)
        if current != record:
            raise conflict("Route batch preview changed")
        writes = {}
        mission, manifest = service.store._load(mission_id)
        for assignment, source, accepted, files, route, matched in prepared:
            _, _, leg = service.store.checked(
                mission_id, assignment.leg_id, request.expected_revision
            )
            leg = next(
                item for item in manifest.expected_legs if item.id == assignment.leg_id
            )
            if service.sources.get_preview(source.id)[1] != source:
                raise conflict("Route batch source changed during preparation")
            previous_identity = leg_identity(leg)
            if leg.route:
                archive_leg(service.store, mission, manifest, leg, "route_replacement")
                manifest.route_history.append(leg.route)
            leg.route = RouteBinding(
                route_id=source.id,
                source_id=source.id,
                content_hash=source.content_hash,
                filename=source.filename,
            )
            leg.review = None
            leg.draft = leg.draft or PlanningDraft()
            leg.draft.evaluation_context = None
            if not leg.draft.ar_corrections:
                leg.draft.ar_corrections = matched
            for reference in manifest.proposal_refs:
                if reference.leg_id == leg.id:
                    reference.state = "stale"
            for proposal in manifest.proposals:
                if proposal.input_identity == previous_identity:
                    proposal.state = "stale"
            manifest.source_revisions.append(accepted)
            manifest.route_bindings.append(leg.route)
            writes.update(files)
        # Discard only unselected staging owned by this batch, in the same commit.
        selected = {source.id for _, source, _, _, _, _ in prepared}
        for attachment_id in record["records"]:
            if attachment_id in selected:
                continue
            _, source, _ = service.sources.acceptance_snapshot(attachment_id)
            if source.owner != mission_id:
                raise conflict("Unselected attachment owner changed")
            writes.update(
                {
                    service.sources.path(source): None,
                    service.sources.root / "staging" / f"{source.id}.source.json": None,
                    service.sources.preview_path(source.id): None,
                }
            )
        manifest.revision += 1
        saved = service.store.persist(mission, manifest, files=writes)
        for _, source, _, _, route, _ in prepared:
            service.store.route_manager.add_route(source.id, route)
        return saved


def discard_routes(service, mission_id, preview_id):
    with storage.get_active_leg_lock(), storage.get_mission_lock(mission_id):
        record, _ = _batch(service, mission_id, preview_id)
        sources = [
            service.sources.get_preview(attachment)[1]
            for attachment in record["records"]
        ]
        if any(source.owner != mission_id for source in sources):
            raise conflict("Route batch owner changed")
        for source in sources:
            service.sources.discard(source)
