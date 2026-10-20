"""Pure correlations over one captured feed; no prediction or durable writes."""

from datetime import timedelta

from .transport_review_models import TransportAssessment, TransportReview
from .transport_windows import communication_windows, overlap


def derive_transport_review(records, events, sources, *, as_of, H):
    models = [s for s in sources if s.source != "operator"]
    fresh = [s for s in models if s.freshness == "fresh" and s.aligned]
    coverage = (
        "available"
        if models
        and all(
            (s.freshness == "fresh" and s.aligned) or s.freshness == "disabled"
            for s in models
        )
        else "partial" if fresh else "unknown"
    )
    activities = communication_windows(records, as_of=as_of)
    result = TransportReview(
        as_of=as_of,
        H=H,
        horizon_end_at=as_of + timedelta(hours=24),
        activities=activities,
        coverage=coverage,
    )
    source_map = {s.source: s for s in sources}
    restrictions = [
        e
        for e in events
        if e.active
        and not e.notification.retired
        and e.kind in ("restriction", "pop_advisory")
        and (e.end_at is None or e.end_at > as_of)
        and (e.due_at is None or e.due_at <= result.horizon_end_at)
    ]
    for record in records:
        if record.deleted or record.record_type != "transport_decision":
            continue
        p = record.payload
        nearby = [
            a
            for a in activities
            if record.leg_id is None or a.leg_id is None or a.leg_id == record.leg_id
        ]
        for row in p.services:
            base = {
                "decision_id": str(record.record_id),
                "row_id": str(row.row_id),
                "service": row.service,
                "dependent_versions": {str(record.record_id): record.version},
            }
            changes = []
            if record.time.planned_start_at is not None:
                changes.append(
                    (
                        record.time.planned_start_at,
                        record.time.planned_end_at or record.time.planned_start_at,
                        "planned_change",
                    )
                )
            if row.applied is not None:
                changes.append(
                    (row.applied.time.at, row.applied.time.at, "reported_application")
                )
            for change_start, change_end, basis in changes or [
                (None, None, "planned_change")
            ]:
                historical = (
                    basis == "reported_application"
                    and change_start is not None
                    and change_start < as_of
                )
                change_activities = (
                    communication_windows(records, as_of=as_of, include_history=True)
                    if historical
                    else nearby
                )
                for activity in change_activities:
                    if (
                        record.leg_id
                        and activity.leg_id
                        and record.leg_id != activity.leg_id
                    ):
                        continue
                    if activity.kind == "conference":
                        continue
                    activity_end = activity.end_at
                    if (
                        activity.ongoing
                        and change_start is not None
                        and change_start <= as_of
                    ):
                        activity_end = as_of + timedelta(microseconds=1)
                    hit = overlap(
                        change_start, change_end, activity.start_at, activity_end
                    )
                    if hit is False:
                        continue
                    if historical and (
                        activity.basis != "operator_reported"
                        or activity.start_at is None
                        or activity_end is None
                    ):
                        hit = None
                    result.assessments.append(
                        TransportAssessment(
                            **(
                                base
                                | {
                                    "dependent_versions": {
                                        **base["dependent_versions"],
                                        activity.record_id: activity.version,
                                    }
                                }
                            ),
                            subject="change_vs_activity",
                            change_basis=basis,
                            report_stage=(
                                "applied"
                                if basis == "reported_application"
                                else "unknown"
                            ),
                            activity_id=activity.record_id,
                            status=(
                                "overlap"
                                if hit
                                else "possible_impact" if change_start else "unknown"
                            ),
                            message=(
                                "Change overlaps customer communications"
                                if hit
                                else "Customer communications may be affected; timing unknown"
                            )
                            + (
                                " · Reported application"
                                if basis == "reported_application"
                                else " · Planned change"
                            ),
                            freshness="fresh"
                        )
                    )
            stages = [
                (name, getattr(row, name).transport)
                for name in ("intended", "requested", "applied")
                if getattr(row, name) is not None
            ]
            for stage, transport in stages or [("unknown", "unknown")]:
                candidates = [a for a in nearby if a.kind != "conference"]
                if not candidates or not restrictions or coverage != "available":
                    result.assessments.append(
                        TransportAssessment(
                            **base,
                            subject="communications_vs_restriction",
                            report_stage=stage,
                            transport=transport,
                            status="unknown",
                            message="Model or customer timing/relevance unavailable; actual routing unknown"
                        )
                    )
                for event in restrictions:
                    if record.leg_id and event.leg_id and record.leg_id != event.leg_id:
                        continue
                    source = source_map.get(event.source_ref)
                    usable = bool(
                        source
                        and source.freshness == "fresh"
                        and source.aligned
                        and event.freshness == "fresh"
                        and not event.notification.preview
                        and event.state != "unknown"
                        and event.due_at
                        and event.end_at
                        and event.time_basis != "live_unavailable"
                    )
                    for activity in candidates:
                        if (
                            activity.leg_id
                            and event.leg_id
                            and activity.leg_id != event.leg_id
                        ):
                            continue
                        linked = bool(
                            (p.call_id and str(p.call_id) == activity.call_id)
                            or (
                                p.conference_id
                                and str(p.conference_id) == activity.conference_id
                            )
                        )
                        relevant = event.transport is None or event.transport == (
                            getattr(getattr(row, stage, None), "transport_id", None)
                            or transport
                        )
                        known_transport = transport != "unknown"
                        hit = overlap(
                            activity.start_at,
                            activity.end_at,
                            event.due_at,
                            event.end_at,
                        )
                        if not usable or coverage != "available" or not known_transport:
                            status = "unknown"
                        elif hit is False or not relevant:
                            status = "no_overlap_found"
                        elif linked and hit:
                            status = "overlap"
                        else:
                            status = "possible_impact"
                        message = {
                            "overlap": "Customer window overlaps modeled restriction",
                            "possible_impact": "Possible customer impact; transport association or timing unknown",
                            "unknown": "Assessment unknown; actual routing unknown",
                            "no_overlap_found": "No overlap found for this report in available inputs",
                        }[status]
                        if event.kind == "pop_advisory":
                            message += " · PoP advisory; not an observed outage"
                        versions = {
                            **base["dependent_versions"],
                            activity.record_id: activity.version,
                        }
                        result.assessments.append(
                            TransportAssessment(
                                **(base | {"dependent_versions": versions}),
                                subject="communications_vs_restriction",
                                report_stage=stage,
                                transport=transport,
                                status=status,
                                message=message,
                                activity_id=activity.record_id,
                                event_ids=[event.event_id],
                                source_refs=(
                                    [event.source_ref] if event.source_ref else []
                                ),
                                time_basis=event.time_basis,
                                freshness="fresh" if usable else "unknown"
                            )
                        )
    return result
