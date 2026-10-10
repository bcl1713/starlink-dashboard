"""Pure source reconciliation and typed archival; publication belongs to the store."""

from uuid import uuid4

from app.mission import storage
from app.mission.models import MissionLegTimeline

from .errors import PlanningFailure
from .identity import planning_identity
from .models import (
    ItineraryPreview,
    LegHistory,
    PlanningDraft,
    PlanningManifest,
    RevisionChange,
    RevisionConflict,
    RevisionLegMapping,
    RevisionPreview,
)

FIELDS = (
    "departure_airport",
    "arrival_airport",
    "departure_time",
    "arrival_time",
    "ar_section_status",
)
AR_FIELDS = (
    "track",
    "entry_time",
    "exit_time",
    "source_time_precision",
    "source_altitude",
)


def invalid(message):
    return PlanningFailure(422, "revision_resolution_required", message)


def revision_identity(manifest):
    return planning_identity(
        manifest.model_dump(exclude={"proposals", "proposal_refs"})
    )


def archive_leg(store, mission, manifest, leg, reason):
    installed = next(
        (item for item in mission.legs if item.id == leg.installed_leg_id), None
    )
    timeline = None
    if installed:
        path = storage.get_leg_timeline_path(installed.id, mission.id)
        if path.exists():
            timeline = MissionLegTimeline.model_validate_json(path.read_bytes())
    manifest.leg_history.append(
        LegHistory(
            leg=leg.model_copy(deep=True),
            installed_leg=installed,
            timeline=timeline,
            source_ids=[source.id for source in manifest.source_revisions],
            revision=manifest.revision,
            reason=reason,
        )
    )


def row_signature(row):
    return tuple(getattr(row, key) for key in AR_FIELDS)


def row_pairs(old, incoming):
    """Unique source evidence only. Duplicate tracks never select a guessed row."""
    used = set()
    result = []
    for row in incoming:
        matches = [
            x
            for x in old
            if x.id not in used and row_signature(x) == row_signature(row)
        ]
        if len(matches) != 1:
            matches = [x for x in old if x.id not in used and x.track == row.track]
            if sum(x.track == row.track for x in incoming) != 1:
                matches = []
        previous = matches[0] if len(matches) == 1 else None
        if previous:
            used.add(previous.id)
        result.append((previous, row))
    return result, [x for x in old if x.id not in used]


def conflicts_for(old, incoming, baseline):
    result = []
    prefix = f"{old.id}:{incoming.id}"
    if baseline is None:
        result.append(
            RevisionConflict(
                id=f"{prefix}:baseline",
                expected_leg_id=old.id,
                field="source_baseline",
                allowed_actions=["retain"],
                message="Prior source extraction unavailable; explicitly acknowledge retained work.",
            )
        )
    if baseline:
        for field in FIELDS:
            if getattr(old, field) != getattr(baseline, field) and getattr(
                old, field
            ) != getattr(incoming, field):
                result.append(
                    RevisionConflict(
                        id=f"{prefix}:field:{field}",
                        expected_leg_id=old.id,
                        field=field,
                        allowed_actions=["retain", "use_source"],
                        message=f"Accepted correction to {field} differs from incoming source; retain it or use source.",
                    )
                )
    rows = baseline.ar_rows if baseline else old.ar_rows
    pairs, removed = row_pairs(rows, incoming.ar_rows)
    corrections = {x.id: x for x in (old.draft.ar_corrections if old.draft else [])}
    for previous, row in pairs:
        if previous and row_signature(previous) != row_signature(row):
            result.append(
                RevisionConflict(
                    id=f"{prefix}:ar:{previous.id}",
                    expected_leg_id=old.id,
                    field="ar_rows",
                    row_id=previous.id,
                    message=f"Source AR {previous.track} changed; retain correction or use incoming source values.",
                )
            )
    for previous in removed:
        result.append(
            RevisionConflict(
                id=f"{prefix}:ar:{previous.id}",
                expected_leg_id=old.id,
                field="ar_rows",
                row_id=previous.id,
                allowed_actions=["retain", "remove"],
                message=f"Source AR {previous.track} removed; retain unresolved correction or explicitly remove it.",
            )
        )
    # Timing/location changes can affect independent manual overlays and locks.
    if (
        any(getattr(old, f) != getattr(incoming, f) for f in FIELDS)
        and old.draft
        and (
            corrections
            or old.draft.manual_aar_tracks
            or old.draft.manual_route_splice
            or old.draft.locks
            or old.draft.unresolved_aar_windows
            or old.draft.unresolved_x_transitions
        )
    ):
        result.append(
            RevisionConflict(
                id=f"{prefix}:manual",
                expected_leg_id=old.id,
                field="manual_work",
                allowed_actions=["retain"],
                message="Leg fields changed. Acknowledge retained manual corrections, pending edits and locks; re-review their anchors.",
            )
        )
    return result


def preview_revision(
    current: PlanningManifest, incoming: ItineraryPreview
) -> RevisionPreview:
    live = [x for x in current.expected_legs if not x.retired]
    parsed = incoming.parsed_values
    pdfs = [s for s in current.source_revisions if s.kind == "itinerary_pdf"]
    baseline = current.itinerary_baseline
    result = RevisionPreview(
        **incoming.model_dump(exclude={"source"}),
        source=incoming.source,
        expected_revision=current.revision,
        input_identity=revision_identity(current),
        old_source_hash=pdfs[-1].content_hash if pdfs else None,
        previous_source_revision=baseline.itinerary_revision if baseline else None,
        identical_content=bool(
            pdfs
            and incoming.source
            and pdfs[-1].content_hash == incoming.source.content_hash
        ),
        lower_revision=bool(
            baseline
            and baseline.itinerary_revision
            and parsed
            and parsed.itinerary_revision
            and parsed.itinerary_revision < baseline.itinerary_revision
        ),
    )
    if not parsed:
        return result
    used = set()
    for new in parsed.expected_legs:
        pair = [
            old
            for old in live
            if (old.departure_airport, old.arrival_airport)
            == (new.departure_airport, new.arrival_airport)
        ]
        # Repeated airport pairs require operator mapping even when ordinal matches.
        if (
            len(pair) == 1
            and sum(
                (x.departure_airport, x.arrival_airport)
                == (new.departure_airport, new.arrival_airport)
                for x in parsed.expected_legs
            )
            == 1
        ):
            old = pair[0]
            if old.id not in used:
                result.leg_mappings.append(
                    RevisionLegMapping(
                        incoming_leg_id=new.id, expected_leg_id=old.id, action="retain"
                    )
                )
                used.add(old.id)
            else:
                result.unresolved_mappings.append(new.id)
        elif not pair:
            result.leg_mappings.append(
                RevisionLegMapping(incoming_leg_id=new.id, action="add")
            )
        else:
            result.unresolved_mappings.append(new.id)
        for old in live:
            previous = (
                next((x for x in baseline.expected_legs if x.id == old.id), None)
                if baseline
                else None
            )
            result.conflicts.extend(conflicts_for(old, new, previous))
            pairs, removed = row_pairs(
                previous.ar_rows if previous else old.ar_rows, new.ar_rows
            )
            for before, after in pairs:
                for field in AR_FIELDS:
                    if before is None or getattr(before, field) != getattr(
                        after, field
                    ):
                        result.changes.append(
                            RevisionChange(
                                field=f"AR {after.track} {field}",
                                expected_leg_id=old.id,
                                incoming_leg_id=new.id,
                                before=str(getattr(before, field)) if before else None,
                                after=str(getattr(after, field)),
                                requires_resolution=before is not None,
                            )
                        )
            for removed_row in removed:
                result.changes.append(
                    RevisionChange(
                        field=f"AR {removed_row.track}",
                        expected_leg_id=old.id,
                        incoming_leg_id=new.id,
                        before=f"{removed_row.entry_time.isoformat()} → {removed_row.exit_time.isoformat()}",
                        after=None,
                        requires_resolution=True,
                    )
                )
            for field in (*FIELDS, "ordinal"):
                if getattr(old, field) != getattr(new, field):
                    result.changes.append(
                        RevisionChange(
                            field=field,
                            expected_leg_id=old.id,
                            incoming_leg_id=new.id,
                            before=str(getattr(old, field)),
                            after=str(getattr(new, field)),
                        )
                    )
            if [row_signature(x) for x in old.ar_rows] != [
                row_signature(x) for x in new.ar_rows
            ]:
                result.changes.append(
                    RevisionChange(
                        field="ar_rows",
                        expected_leg_id=old.id,
                        incoming_leg_id=new.id,
                        before=str(len(old.ar_rows)),
                        after=str(len(new.ar_rows)),
                        requires_resolution=True,
                    )
                )
    if not result.unresolved_mappings:
        result.leg_mappings.extend(
            RevisionLegMapping(
                incoming_leg_id="", expected_leg_id=x.id, action="retire"
            )
            for x in live
            if x.id not in used
        )
    if baseline:
        for field in ("name", "aircraft", "call_sign", "itinerary_revision"):
            if getattr(baseline, field) != getattr(parsed, field):
                result.changes.append(
                    RevisionChange(
                        field=field,
                        before=str(getattr(baseline, field)),
                        after=str(getattr(parsed, field)),
                    )
                )
    return result


def reconcile(current, preview, request):
    parsed = request.itinerary or preview.parsed_values
    if not parsed or not parsed.expected_legs:
        raise invalid("Correct extraction errors and provide expected legs")
    if request.itinerary is None and not preview.confirmable:
        raise invalid("Correct extraction errors before applying this revision")
    for leg in parsed.expected_legs:
        if leg.route or leg.draft or leg.review or leg.installed_leg_id or leg.retired:
            raise invalid(
                "Revision input cannot contain server-owned bindings, drafts or reviews"
            )
        if any(
            row.start_anchor
            or row.end_anchor
            or row.confirmed
            or row.match_status != "unresolved"
            for row in leg.ar_rows
        ):
            raise invalid(
                "Source corrections cannot supply route anchors or review confirmations"
            )
    live = {x.id: x for x in current.expected_legs if not x.retired}
    incoming = {x.id: x for x in parsed.expected_legs}
    if len(incoming) != len(parsed.expected_legs) or sorted(
        x.ordinal for x in incoming.values()
    ) != list(range(1, len(incoming) + 1)):
        raise invalid("Incoming IDs and ordinals must be unique and contiguous")
    mapped_incoming, mapped_old = set(), set()
    for mapping in request.leg_mappings:
        if mapping.action != "retire":
            if (
                mapping.incoming_leg_id not in incoming
                or mapping.incoming_leg_id in mapped_incoming
            ):
                raise invalid("Map each incoming leg exactly once")
            mapped_incoming.add(mapping.incoming_leg_id)
        if mapping.action != "add":
            if (
                mapping.expected_leg_id not in live
                or mapping.expected_leg_id in mapped_old
            ):
                raise invalid(
                    "Map each existing leg exactly once or explicitly retire it"
                )
            mapped_old.add(mapping.expected_leg_id)
        elif mapping.expected_leg_id is not None:
            raise invalid("New legs cannot claim existing IDs")
    if mapped_incoming != set(incoming) or mapped_old != set(live):
        raise invalid("Resolve all incoming and existing leg mappings")
    resolutions = {x.conflict_id: x for x in request.correction_resolutions}
    if len(resolutions) != len(request.correction_resolutions):
        raise invalid("Duplicate correction resolution")
    required = set()
    revised = current.model_copy(deep=True)
    revised.expected_legs = [x for x in revised.expected_legs if x.retired]
    source_baseline = []

    def record_baseline(incoming_id, stable_id, row_ids):
        raw = (
            next(
                (x for x in preview.parsed_values.expected_legs if x.id == incoming_id),
                None,
            )
            if preview.parsed_values
            else None
        )
        if raw:
            source_baseline.append(
                raw.model_copy(
                    update={
                        "id": stable_id,
                        "ar_rows": [
                            row.model_copy(
                                update={"id": row_ids.get(row.id, row.id)}, deep=True
                            )
                            for row in raw.ar_rows
                        ],
                    },
                    deep=True,
                )
            )

    for mapping in request.leg_mappings:
        if mapping.action == "retire":
            old = live[mapping.expected_leg_id].model_copy(deep=True)
            old.retired = True
            old.installed_leg_id = None
            revised.expected_legs.append(old)
            continue
        new = incoming[mapping.incoming_leg_id]
        if mapping.action == "add":
            added = new.model_copy(
                update={"id": str(uuid4()), "draft": PlanningDraft()}, deep=True
            )
            revised.expected_legs.append(added)
            record_baseline(new.id, added.id, {})
            continue
        old = live[mapping.expected_leg_id]
        baseline = (
            next(
                (x for x in current.itinerary_baseline.expected_legs if x.id == old.id),
                None,
            )
            if current.itinerary_baseline
            else None
        )
        conflicts = conflicts_for(old, new, baseline)
        required.update(x.id for x in conflicts)
        if any(x.id not in resolutions for x in conflicts):
            raise invalid(
                "Resolve each changed source row and manual correction conflict"
            )
        for issue in conflicts:
            if resolutions[issue.id].action not in issue.allowed_actions:
                raise invalid("Choose a supported action for each named correction")
            if (
                issue.field in {"manual_work", "source_baseline"}
                and resolutions[issue.id].action != "retain"
            ):
                raise invalid(
                    "Manual work and unknown baseline must be explicitly retained"
                )
        updated = old.model_copy(deep=True)
        for field in (*FIELDS, "ordinal"):
            choice = resolutions.get(f"{old.id}:{new.id}:field:{field}")
            if choice and choice.action == "remove":
                raise invalid("Required leg fields cannot be removed")
            setattr(
                updated,
                field,
                getattr(old if choice and choice.action == "retain" else new, field),
            )
        pairs, removed = row_pairs(
            baseline.ar_rows if baseline else old.ar_rows, new.ar_rows
        )
        source_rows = []
        row_ids = {}
        corrections = {
            x.id: x.model_copy(deep=True)
            for x in (
                (old.draft.ar_corrections or old.ar_rows) if old.draft else old.ar_rows
            )
        }
        for previous, row in pairs:
            stable_row_id = previous.id if previous else str(uuid4())
            row_ids[row.id] = stable_row_id
            row = row.model_copy(update={"id": stable_row_id}, deep=True)
            source_rows.append(row)
            key = f"{old.id}:{new.id}:ar:{row.id}"
            choice = resolutions.get(key)
            if previous is None or (choice and choice.action == "use_source"):
                corrections[row.id] = row.model_copy(deep=True)
            elif choice and choice.action == "remove":
                corrections[row.id] = row.model_copy(
                    update={
                        "match_status": "excluded",
                        "exclusion_note": "Explicitly removed during itinerary revision",
                        "confirmed": False,
                    },
                    deep=True,
                )
        for row in removed:
            choice = resolutions[f"{old.id}:{new.id}:ar:{row.id}"]
            if choice.action == "use_source":
                raise invalid("A removed source row requires retain or remove")
            if choice.action == "remove":
                corrections.pop(row.id, None)
        updated.ar_rows = source_rows
        # Only reset corrected review data when source fields actually changed.
        same_source = all(getattr(old, f) == getattr(updated, f) for f in FIELDS) and [
            row_signature(x) for x in old.ar_rows
        ] == [row_signature(x) for x in source_rows]
        if same_source:
            updated.ar_rows = [row.model_copy(deep=True) for row in old.ar_rows]
        else:
            updated.review = None
            updated.draft = updated.draft or PlanningDraft()
            updated.draft.ar_corrections = list(corrections.values())
            updated.draft.evaluation_context = None
            updated.draft.no_ars_confirmed = False
            for row in updated.draft.ar_corrections:
                row.confirmed = False
        revised.expected_legs.append(updated)
        record_baseline(new.id, old.id, row_ids)
    if set(resolutions) != required:
        raise invalid("Correction resolution does not belong to the selected mappings")
    revised.itinerary_baseline = (
        preview.parsed_values.model_copy(
            update={"expected_legs": source_baseline}, deep=True
        )
        if preview.parsed_values
        else None
    )
    return PlanningManifest.model_validate(revised.storage_record())
