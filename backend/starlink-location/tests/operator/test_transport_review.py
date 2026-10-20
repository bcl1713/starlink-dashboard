"""Pure advisory correlation never claims a measured path or stale all-clear."""

from datetime import timedelta

from app.operator.event_models import OperationalEvent, SourceCapture
from tests.operator.service_helpers import create
from tests.operator.test_transport_contract import decision, row


def review(records, events, clock, sources=None):
    from app.operator.transport_review import derive_transport_review

    return derive_transport_review(
        records, events, sources or [], as_of=clock.now(), H=12
    )


def call(service, record_data, clock, **changes):
    return create(
        service,
        record_data,
        record_type="call",
        time={
            "planned_start_at": clock.now().isoformat(),
            "planned_end_at": (clock.now() + timedelta(minutes=20)).isoformat(),
        },
        payload={
            "entry_type": "call",
            "title": "Synthetic VTC",
            "prep_lead_minutes": 10,
            **changes,
        },
    )


def restriction(clock, **changes):
    return OperationalEvent(
        event_id="x-event",
        mission_id="demo-mission",
        leg_id="leg-a",
        kind="restriction",
        title="X modeled restriction",
        source_ref="model:leg-a",
        source_revision="r1",
        provenance="modeled",
        state="active",
        time_basis="live_route_eta",
        due_at=clock.now(),
        end_at=clock.now() + timedelta(minutes=10),
        transport="X",
        significance="unavailable",
        **changes
    )


def test_independent_reports_and_active_call_warning(service, record_data, clock):
    customer = call(service, record_data, clock)
    data = decision(
        record_data,
        row(
            intended={"transport": "Ka"},
            requested={"transport": "X"},
            applied={"transport": "Starshield"},
            checked={"result": "satisfactory"},
        ),
    )
    data["payload"]["call_id"] = str(customer.record_id)
    data["time"] = {"planned_start_at": clock.now().isoformat()}
    saved = create(service, data)
    source = SourceCapture(
        source="model:leg-a", freshness="fresh", aligned=True, guardable=True
    )
    result = review([customer, saved], [restriction(clock)], clock, [source])
    assert result.actual_routing == "unknown"
    assert any(
        a.subject == "change_vs_activity" and a.status == "overlap"
        for a in result.assessments
    )
    matched = [a for a in result.assessments if a.event_ids]
    assert any(a.report_stage == "requested" and a.status == "overlap" for a in matched)
    assert any(
        a.report_stage == "applied" and a.status == "no_overlap_found" for a in matched
    )


def test_stale_model_never_all_clear(service, record_data, clock):
    saved = create(service, decision(record_data, row(applied={"transport": "Ka"})))
    result = review(
        [saved],
        [restriction(clock)],
        clock,
        [SourceCapture(source="model:leg-a", freshness="stale")],
    )
    assert result.coverage == "unknown"
    assert not any(a.status == "no_overlap_found" for a in result.assessments)


def test_half_open_and_unknown_boundaries(clock):
    from app.operator.transport_windows import overlap

    now = clock.now()
    assert (
        overlap(
            now,
            now + timedelta(minutes=1),
            now + timedelta(minutes=1),
            now + timedelta(minutes=2),
        )
        is False
    )
    assert overlap(now, now, now, now + timedelta(minutes=1)) is True
    assert overlap(None, None, now, now + timedelta(minutes=1)) is None


def test_no_inferred_service_association_or_other_leg(service, record_data, clock):
    customer = call(service, record_data, clock)
    data = decision(record_data, row(requested={"transport": "X"}))
    data["time"] = {"planned_start_at": clock.now().isoformat()}
    saved = create(service, data)
    result = review(
        [customer, saved],
        [restriction(clock)],
        clock,
        [SourceCapture(source="model:leg-a", freshness="fresh", aligned=True)],
    )
    assert any(
        a.status == "possible_impact" and a.subject == "communications_vs_restriction"
        for a in result.assessments
    )
    assert all(
        a.status != "overlap"
        for a in result.assessments
        if a.subject == "communications_vs_restriction"
    )


def test_completed_call_does_not_end_customer_or_conference(
    service, record_data, clock
):
    customer = call(service, record_data, clock, status="completed")
    conference = create(
        service,
        record_data,
        record_type="conference",
        payload={
            "entry_type": "conference",
            "title": "Shared",
            "status": "established",
        },
    )
    participation = create(
        service,
        record_data,
        record_type="participation",
        time={},
        payload={
            "entry_type": "participation",
            "title": "Connected",
            "call_id": str(customer.record_id),
            "conference_id": str(conference.record_id),
            "state": "connected",
        },
    )
    from app.operator.transport_windows import communication_windows

    windows = communication_windows(
        [customer, conference, participation], as_of=clock.now()
    )
    assert not any(w.kind == "call" for w in windows)
    assert {w.kind for w in windows} == {"conference", "connected"}


def test_instant_is_symmetric_at_start(clock):
    from app.operator.transport_windows import overlap

    now = clock.now()
    assert overlap(now, now + timedelta(minutes=1), now, now) is True


def test_retrospective_application_uses_known_completed_call(
    service, record_data, clock
):
    customer = create(
        service,
        record_data,
        record_type="call",
        payload={"entry_type": "call", "title": "Completed", "status": "completed"},
    )
    data = decision(
        record_data,
        row(
            applied={
                "transport": "Ka",
                "time": {"at": "2026-10-17T14:35:00Z", "precision": "exact"},
            }
        ),
    )
    data["time"] = {}
    saved = create(service, data)
    result = review([customer, saved], [], clock)
    assert any(
        a.subject == "change_vs_activity" and a.status == "overlap"
        for a in result.assessments
    )


def test_planned_change_does_not_hide_reported_application(service, record_data, clock):
    customer = create(
        service,
        record_data,
        record_type="call",
        payload={
            "entry_type": "call",
            "title": "Completed customer",
            "status": "completed",
        },
    )
    data = decision(
        record_data,
        row(
            applied={
                "transport": "Ka",
                "time": {"at": "2026-10-17T14:35:00Z", "precision": "exact"},
            }
        ),
    )
    data["time"] = {"planned_start_at": "2026-10-17T17:00:00Z"}
    saved = create(service, data)
    result = review([customer, saved], [], clock)
    assert any(
        a.subject == "change_vs_activity" and a.status == "overlap"
        for a in result.assessments
    )


def test_retrospective_application_uses_ended_participation(
    service, record_data, clock
):
    conference = create(
        service,
        record_data,
        record_type="conference",
        payload={"entry_type": "conference", "title": "Shared", "status": "closed"},
    )
    participant = create(
        service,
        record_data,
        record_type="participation",
        payload={
            "entry_type": "participation",
            "title": "Customer left",
            "conference_id": str(conference.record_id),
            "state": "left",
        },
    )
    data = decision(
        record_data,
        row(
            applied={
                "transport": "X",
                "time": {"at": "2026-10-17T14:35:00Z", "precision": "exact"},
            }
        ),
    )
    data["time"] = {}
    saved = create(service, data)
    result = review([conference, participant, saved], [], clock)
    assert any(
        a.activity_id == str(participant.record_id) and a.status == "overlap"
        for a in result.assessments
    )


def test_catalog_display_name_matches_canonical_restriction(
    service, record_data, clock
):
    from app.operator.catalog import CatalogStore

    customer = call(service, record_data, clock)
    store = CatalogStore(service.store.settings.root / "transport-catalog.json")
    store.update(store.read())
    data = decision(
        record_data, row(applied={"transport": "X-band", "transport_id": "X"})
    )
    data["payload"]["call_id"] = str(customer.record_id)
    saved = create(service, data)
    source = SourceCapture(
        source="model:leg-a", freshness="fresh", aligned=True, guardable=True
    )
    result = review([customer, saved], [restriction(clock)], clock, [source])
    assert any(
        a.subject == "communications_vs_restriction" and a.status == "overlap"
        for a in result.assessments
    )
