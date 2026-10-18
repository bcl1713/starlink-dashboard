"""Synthetic-only controlled inputs; uses actual #348 prediction and continuity."""

import copy
import json
import threading
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.mission.pop_capabilities import capture_call_capabilities
from app.mission.pop_status import PopStatusService
from app.operator.errors import OperatorError
from app.operator.event_models import SourceCapture
from app.operator.event_policy import EventPolicy
from app.operator.event_sources import EventSourceAdapter
from app.operator.models import CreateRecord
from app.operator.time_models import utc_timestamp
from scenario import RUN_ID, START, ScenarioClock, pop_inputs

MISSION = "synthetic-mission-a"
LEG = "synthetic-leg-1"


class EventsClock(ScenarioClock):
    def __init__(self, root):
        path = Path(root) / "operator" / "synthetic-event-source.json"
        state = json.loads(path.read_text()) if path.exists() else {}
        super().__init__(utc_timestamp(state.get("now", START)))

    def set(self, value):
        value = utc_timestamp(value)
        self.elapsed += max(0, (value - self.current).total_seconds())
        self.current = value


def seed_events(service, clock):
    """Deterministic keys and fixed planned times preserve writes on restart."""
    ids = {}
    specifications = [
        (
            "alpha",
            "call",
            {
                "entry_type": "call",
                "title": "Synthetic customer alpha",
                "status": "scheduled",
                "prep_lead_minutes": 10,
            },
            {
                "planned_start_at": START + timedelta(minutes=12),
                "planned_end_at": START + timedelta(minutes=28),
            },
        ),
        (
            "beta",
            "call",
            {
                "entry_type": "call",
                "title": "Synthetic customer beta",
                "status": "scheduled",
                "prep_lead_minutes": 10,
            },
            {
                "planned_start_at": START + timedelta(minutes=14),
                "planned_end_at": START + timedelta(minutes=30),
            },
        ),
        (
            "canceled",
            "call",
            {
                "entry_type": "call",
                "title": "Synthetic canceled requirement",
                "status": "cancelled",
            },
            {"planned_start_at": START + timedelta(minutes=6)},
        ),
        (
            "followup",
            "issue",
            {
                "entry_type": "issue",
                "title": "Synthetic overdue follow-up",
                "status": "open",
                "follow_up_at": START - timedelta(minutes=10),
            },
            {},
        ),
        (
            "conference",
            "conference",
            {
                "entry_type": "conference",
                "title": "Synthetic customer room",
                "status": "closed",
                "configured_transport": "Ka",
            },
            {},
        ),
    ]
    epoch = str(service.store.health().api_epoch)
    for name, kind, payload, timing in specifications:
        command = CreateRecord(
            record_type=kind,
            mission_id=MISSION,
            leg_id=None,
            scope="mission",
            time=timing,
            payload=payload,
        )
        receipt = service.execute(
            command,
            key=str(uuid5(NAMESPACE_URL, "operator-events/" + name)),
            epoch=epoch,
        )
        ids[name] = str(receipt.saved_records[0].record_id)
    for name, call, conference in (
        ("linked", ids["alpha"], ids["conference"]),
        ("call-only", ids["beta"], None),
        ("conference-only", None, ids["conference"]),
    ):
        command = CreateRecord(
            record_type="participation",
            mission_id=MISSION,
            scope="mission",
            time={},
            payload={
                "entry_type": "participation",
                "title": "Synthetic " + name,
                "state": "connected",
                "call_id": call,
                "conference_id": conference,
            },
        )
        service.execute(
            command,
            key=str(uuid5(NAMESPACE_URL, "operator-events/" + name)),
            epoch=epoch,
        )
    return ids


class EventsFixture:
    """All input writers participate; no real source is designated guardable."""

    def __init__(self, runtime, root, clock):
        self.runtime, self.root, self.clock = runtime, Path(root), clock
        self.path = self.root / "operator" / "synthetic-event-source.json"
        self.state = (
            json.loads(self.path.read_text())
            if self.path.exists()
            else {
                "now": START.isoformat(),
                "longitude": 3.5,
                "fallback": None,
                "available": True,
                "enabled": True,
                "generation": 0,
                "timing_basis": "mission",
            }
        )
        self._writer = threading.RLock()
        self.race_once = False
        self.current = None
        self.pop = PopStatusService(observation_provider=lambda *_: self.observation)
        self.ids = seed_events(runtime.service, clock)
        runtime.event_policy = EventPolicy(
            model_shift_seconds=20.0, model_capture_spacing_seconds=1.0
        )
        self.update({})
        original_guard = runtime.event_publication.guard

        @contextmanager
        def guard(expected):
            if expected and self.race_once:
                self.race_once = False
                failure = []

                def replace_prediction():
                    try:
                        self.update({"longitude": 4.0, "timing_basis": "live"})
                    except BaseException as error:
                        failure.append(error)

                thread = threading.Thread(
                    target=replace_prediction, name="synthetic-event-publication"
                )
                thread.start()
                thread.join(timeout=3)
                if thread.is_alive() or failure:
                    raise OperatorError("event_source_unavailable")
            with original_guard(expected):
                yield

        runtime.event_publication.guard = guard
        self.adapter = self.Adapter(self)
        runtime.event_source_adapter = self.adapter

    def update(self, changes):
        allowed = {
            "now",
            "longitude",
            "fallback",
            "available",
            "enabled",
            "arm_ack_race",
            "timing_basis",
        }
        if set(changes) - allowed:
            raise ValueError("Unknown synthetic control")
        with self._writer:
            if set(changes) == {"arm_ack_race"}:
                self.race_once = bool(changes["arm_ack_race"])
                return {
                    "synthetic": True,
                    "raceArmed": self.race_once,
                    "generation": self.current[0].generation,
                }
            state = self.state | {
                k: v for k, v in changes.items() if k != "arm_ack_race"
            }
            now = utc_timestamp(state["now"])
            longitude = state["longitude"]
            if not isinstance(longitude, (int, float)) or not -10 <= longitude <= 10:
                raise ValueError("Synthetic longitude outside fixture")
            if (
                state["fallback"] not in (None, "Ka", "X")
                or type(state["available"]) is not bool
                or type(state["enabled"]) is not bool
            ):
                raise ValueError("Invalid synthetic source state")
            inputs = pop_inputs(ScenarioClock(START), fallback=state["fallback"])
            timeline = inputs.pop("timeline")
            projector = inputs.pop("projector")
            sample = inputs.pop("telemetry")
            self.observation = inputs.pop("observation")
            sample.position.longitude = longitude
            sample.position.observed_at = now if state["available"] else None
            sample.position.speed_observed_at = now
            inputs.update(
                now=now,
                observed_now=now,
                enabled=state["enabled"],
                mission_id=MISSION,
                leg_id=LEG,
                simulation_run_id=RUN_ID,
            )
            caps = capture_call_capabilities(timeline, inputs["route"], projector)
            if state.get("timing_basis", "mission") == "mission":
                inputs["projector"] = projector
            elif state["timing_basis"] != "live":
                raise ValueError("Unknown synthetic timing basis")
            publication = self.pop.snapshot(sample, call_capabilities=caps, **inputs)
            model = timeline.model_dump(mode="json")
            model.update(publication)
            state["generation"] += 1
            source = SourceCapture(
                source="model:" + LEG,
                revision=publication["pop_forecast"]["revision"],
                generation=str(state["generation"]),
                input_identity="synthetic-route-a-b-v1",
                captured_at=now,
                freshness=(
                    "disabled"
                    if not state["enabled"]
                    else (
                        "fresh"
                        if publication["pop_forecast"]["status"] == "ready"
                        else "unknown"
                    )
                ),
                aligned=True,
                guardable=True,
                reason="Wholly synthetic participating fixture inputs",
            )

            def commit_inputs():
                self.clock.set(now)
                self.state = state
                self.current = (source, model)
                self.path.write_text(json.dumps(state, default=str))
                self.race_once = bool(changes.get("arm_ack_race", self.race_once))

            self.runtime.event_publication.publish(source, update=commit_inputs)
            return {
                "synthetic": True,
                "generation": source.generation,
                "modelStatus": publication["pop_forecast"]["status"],
                "now": now.isoformat(),
                "ids": self.ids,
            }

    class Adapter:
        def __init__(self, fixture):
            self.fixture = fixture

        def capture(self, mission_id, *, as_of):
            fixture = self.fixture
            captured = EventSourceAdapter(fixture.runtime.service).capture(
                mission_id, as_of=as_of
            )
            if mission_id != MISSION:
                return captured
            source, model = fixture.current
            return replace(
                captured,
                sources=[s for s in captured.sources if s.source != source.source]
                + [source.model_copy(deep=True)],
                models=captured.models | {LEG: copy.deepcopy(model)},
            )


def exercise_fixture(root):
    from app.mission import storage
    from app.operator.runtime import OperatorRuntime
    from app.operator.settings import OperatorSettings
    from seed import seed_demo

    clock = EventsClock(root)
    seeded = seed_demo(root, clock=clock, mode="simulation")
    previous = storage.MISSIONS_DIR
    storage.MISSIONS_DIR = Path(root) / "missions"
    runtime = OperatorRuntime.start(
        OperatorSettings(
            enabled=True,
            root=Path(root) / "operator",
            source_mode="simulation",
            simulation_run_id=seeded["run_id"],
        ),
        clock=clock,
    )
    try:
        fixture = EventsFixture(runtime, root, clock)
        first = fixture.adapter.capture(MISSION, as_of=clock.now())
        source = next(s for s in first.sources if s.source == "model:" + LEG)
        assert first.models[LEG]["pop_forecast"]["transitions"]
        assert first.models[LEG]["call_continuity"]["pop_call_outage_seconds"] == 600
        for fallback in ("Ka", "X"):
            fixture.update({"fallback": fallback})
            assert fixture.current[1]["call_continuity"]["pop_call_outage_seconds"] == 0
        fixture.update({"longitude": 4.0, "timing_basis": "live"})
        live_window = fixture.current[1]["pop_forecast"]["transitions"][0][
            "crossing_utc"
        ]
        assert (
            live_window
            != first.models[LEG]["pop_forecast"]["transitions"][0]["crossing_utc"]
        )
        assert fixture.current[1]["call_continuity"] is None
        try:
            with runtime.event_publication.guard((source,)):
                raise AssertionError("Old prediction was admitted")
        except OperatorError as error:
            assert error.code == "event_snapshot_changed"
        fixture.update({"available": False})
        last = fixture.adapter.capture(MISSION, as_of=clock.now())
        assert (
            next(s for s in last.sources if s.source == "model:" + LEG).freshness
            == "unknown"
        )
        return {
            "realForecast": True,
            "changedGeneration": True,
            "unguardedMutationRejected": True,
            "sourceFailureUnknown": True,
        }
    finally:
        runtime.close()
        storage.MISSIONS_DIR = previous
