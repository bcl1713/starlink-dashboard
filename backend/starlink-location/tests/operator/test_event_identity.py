"""Prediction revisions cannot re-arm alerts; sustained material shifts can."""

from datetime import timedelta


def test_prediction_drift_is_measured_from_accepted_anchor(service, clock):
    from app.operator.event_identity import ModelStability
    from app.operator.event_ledger import reconcile
    from app.operator.event_models import OperationalEvent
    from app.operator.event_policy import EventPolicy

    policy, stability = EventPolicy(), ModelStability()
    base = OperationalEvent(
        event_id="model-a",
        mission_id="demo-mission",
        kind="restriction",
        provenance="modeled",
        title="Synthetic restriction",
        due_at=clock.now() + timedelta(minutes=20),
        end_at=clock.now() + timedelta(minutes=30),
        schedule_key="route-family",
        freshness="fresh",
    )

    def save(event):
        with service.store.connect(write=True) as db:
            return reconcile(
                db, [event], as_of=clock.now(), policy=policy, stability=stability
            )[0]

    first = save(base)
    drift = base.model_copy(
        update={
            "due_at": base.due_at + timedelta(seconds=299),
            "source_revision": "refresh",
        }
    )
    assert save(drift).notification.generation == first.notification.generation
    moved = base.model_copy(update={"due_at": base.due_at + timedelta(seconds=300)})
    assert save(moved).notification.generation == first.notification.generation
    clock.advance(14)
    assert save(moved).notification.generation == first.notification.generation
    clock.advance(1)
    second = save(moved)
    assert second.notification.generation != first.notification.generation
    assert save(moved).notification.generation == second.notification.generation


def test_accepted_escalation_stays_stable_on_following_poll(service, clock):
    from app.operator.event_identity import ModelStability
    from app.operator.event_ledger import reconcile
    from app.operator.event_models import EventNotification, OperationalEvent
    from app.operator.event_policy import EventPolicy

    stability, policy = ModelStability(), EventPolicy()
    base = OperationalEvent(
        event_id="restriction",
        mission_id="demo-mission",
        kind="restriction",
        provenance="modeled",
        title="Synthetic",
        due_at=clock.now() + timedelta(minutes=10),
        schedule_key="family",
        notification=EventNotification(severity_generation=1),
    )

    def save(event):
        with service.store.connect(write=True) as db:
            return reconcile(
                db, [event], as_of=clock.now(), policy=policy, stability=stability
            )[0]

    first = save(base)
    escalated = base.model_copy(deep=True)
    escalated.notification.severity_generation = 2
    assert save(escalated).notification.severity_generation == 1
    clock.advance(15)
    assert save(escalated).notification.severity_generation == 2
    # A committed accepted tier survives the next refresh and a controller restart.
    stability = ModelStability()
    assert save(escalated).notification.severity_generation == 2
    assert save(escalated).notification.generation == first.notification.generation


def test_ambiguous_split_is_visual_until_stable_captures(service, clock):
    from app.operator.event_identity import ModelStability
    from app.operator.event_ledger import reconcile
    from app.operator.event_models import OperationalEvent
    from app.operator.event_policy import EventPolicy

    stability, policy = ModelStability(), EventPolicy()
    base = OperationalEvent(
        event_id="segment-0",
        family_key="route-ka",
        mission_id="demo-mission",
        kind="restriction",
        provenance="modeled",
        title="Synthetic",
        due_at=clock.now() + timedelta(minutes=10),
        end_at=clock.now() + timedelta(minutes=30),
        schedule_key="family",
    )

    def save(events):
        with service.store.connect(write=True) as db:
            return reconcile(
                db, events, as_of=clock.now(), policy=policy, stability=stability
            )

    save([base])
    split = [
        base.model_copy(update={"end_at": base.due_at + timedelta(minutes=5)}),
        base.model_copy(
            update={
                "event_id": "segment-1",
                "due_at": base.due_at + timedelta(minutes=8),
            }
        ),
    ]
    assert all(not e.notification.available for e in save(split))
    clock.advance(15)
    assert all(e.notification.available for e in save(split))


def test_unstable_split_previews_do_not_write_each_forecast_refresh(service, clock):
    from app.operator.event_identity import ModelStability
    from app.operator.event_ledger import reconcile
    from app.operator.event_models import OperationalEvent
    from app.operator.event_policy import EventPolicy

    stability, policy = ModelStability(), EventPolicy()
    base = OperationalEvent(
        event_id="initial",
        family_key="family",
        mission_id="demo-mission",
        kind="restriction",
        provenance="modeled",
        title="Synthetic",
        due_at=clock.now() + timedelta(minutes=10),
        end_at=clock.now() + timedelta(minutes=30),
        schedule_key="source",
    )
    with service.store.connect(write=True) as db:
        reconcile(db, [base], as_of=clock.now(), policy=policy, stability=stability)
        for second in range(5):
            split = [
                base.model_copy(
                    update={
                        "end_at": base.due_at + timedelta(minutes=5, seconds=second)
                    }
                ),
                base.model_copy(
                    update={
                        "event_id": "second",
                        "due_at": base.due_at + timedelta(minutes=8, seconds=second),
                    }
                ),
            ]
            previews = reconcile(
                db, split, as_of=clock.now(), policy=policy, stability=stability
            )
            assert all(event.notification.generation is None for event in previews)
            assert db.execute("SELECT count(*) FROM event_occurrences").fetchone() == (
                1,
            )
            clock.advance(1)


def test_split_requires_consecutive_fresh_materially_consistent_captures(
    service, clock
):
    from app.operator.event_identity import ModelStability
    from app.operator.event_ledger import reconcile
    from app.operator.event_models import OperationalEvent
    from app.operator.event_policy import EventPolicy

    stability, policy = ModelStability(), EventPolicy()
    base = OperationalEvent(
        event_id="initial",
        family_key="route",
        mission_id="demo-mission",
        kind="restriction",
        provenance="modeled",
        title="Synthetic",
        due_at=clock.now() + timedelta(minutes=10),
        end_at=clock.now() + timedelta(minutes=45),
        schedule_key="route",
        freshness="fresh",
    )

    def save(events):
        with service.store.connect(write=True) as db:
            return reconcile(
                db, events, as_of=clock.now(), policy=policy, stability=stability
            )

    save([base])
    split = [
        base.model_copy(
            update={"end_at": base.due_at + timedelta(minutes=8), "freshness": "stale"}
        ),
        base.model_copy(
            update={
                "event_id": "second",
                "due_at": base.due_at + timedelta(minutes=15),
                "freshness": "stale",
            }
        ),
    ]
    assert all(e.notification.preview for e in save(split))
    clock.advance(15)
    fresh = [e.model_copy(update={"freshness": "fresh"}, deep=True) for e in split]
    assert all(e.notification.preview for e in save(fresh))
    clock.advance(15)
    moved = [
        e.model_copy(
            update={
                "due_at": e.due_at + timedelta(minutes=6),
                "end_at": e.end_at + timedelta(minutes=6),
            },
            deep=True,
        )
        for e in fresh
    ]
    assert all(e.notification.preview for e in save(moved))
    clock.advance(15)
    assert all(not e.notification.preview for e in save(moved))
