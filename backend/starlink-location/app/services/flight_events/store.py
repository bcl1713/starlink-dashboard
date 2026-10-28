"""Transactional event ledger, observation state, outbox, and history pins."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.services.flight_events.detector import advance_detection
from app.services.flight_events.models import (
    DetectionPolicy,
    DetectionState,
    FlightEvent,
    FlightObservation,
)


class FlightEventStore:
    """Use one local persistent volume; SQLite serializes competing workers."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS states (
                    mission TEXT, leg TEXT, payload TEXT NOT NULL,
                    PRIMARY KEY (mission, leg));
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT, revision INTEGER, mission TEXT, leg TEXT,
                    payload TEXT NOT NULL, PRIMARY KEY (id, revision));
                CREATE TABLE IF NOT EXISTS outbox (
                    id TEXT, revision INTEGER, acknowledged INTEGER DEFAULT 0,
                    PRIMARY KEY (id, revision));
                CREATE TABLE IF NOT EXISTS pins (
                    mission TEXT, leg TEXT, start TEXT NOT NULL,
                    PRIMARY KEY (mission, leg));
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        try:
            db.execute("PRAGMA foreign_keys=ON")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _state(self, db, mission_id, leg_id):
        row = db.execute(
            "SELECT payload FROM states WHERE mission=? AND leg=?", (mission_id, leg_id)
        ).fetchone()
        return DetectionState.model_validate_json(row[0]) if row else DetectionState()

    def state(self, mission_id: str, leg_id: str) -> DetectionState:
        with self.connect() as db:
            return self._state(db, mission_id, leg_id)

    def break_continuity(self) -> None:
        """Mode changes interrupt pending inference, never confirmed history."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for mission, leg, payload in db.execute(
                "SELECT mission, leg, payload FROM states"
            ).fetchall():
                state = DetectionState.model_validate_json(payload)
                state.candidate = None
                state.uncertain = True
                self._save_state(db, mission, leg, state)

    def _save_state(self, db, mission_id, leg_id, state):
        db.execute(
            "INSERT OR REPLACE INTO states VALUES (?, ?, ?)",
            (mission_id, leg_id, state.model_dump_json()),
        )

    def _append(self, db, event):
        db.execute(
            "INSERT INTO events VALUES (?, ?, ?, ?, ?)",
            (
                event.event_id,
                event.revision,
                event.mission_id,
                event.leg_id,
                event.model_dump_json(),
            ),
        )
        db.execute(
            "INSERT INTO outbox(id, revision) VALUES (?, ?)",
            (event.event_id, event.revision),
        )

    def _events(self, db, mission_id, leg_id):
        rows = db.execute(
            "SELECT e.payload FROM events e JOIN (SELECT id, MAX(revision) AS rev FROM events GROUP BY id) latest ON latest.id=e.id AND latest.rev=e.revision WHERE mission=? AND leg=?",
            (mission_id, leg_id),
        ).fetchall()
        return sorted(
            [FlightEvent.model_validate_json(row[0]) for row in rows],
            key=lambda event: (event.occurred_at, event.detected_at, event.event_id),
        )

    def events(self, mission_id: str, leg_id: str) -> list[FlightEvent]:
        with self.connect() as db:
            return self._events(db, mission_id, leg_id)

    def apply_observation(
        self, observation: FlightObservation, policy: DetectionPolicy | None = None
    ):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            state = self._state(db, observation.mission_id, observation.leg_id)
            result = advance_detection(state, observation, policy or DetectionPolicy())
            self._save_state(
                db, observation.mission_id, observation.leg_id, result.state
            )
            for event in result.emitted_events:
                self._append(db, event)
            candidate = result.state.candidate
            if candidate and candidate.kind == "off_blocks":
                db.execute(
                    "INSERT OR REPLACE INTO pins VALUES (?, ?, ?)",
                    (
                        observation.mission_id,
                        observation.leg_id,
                        (candidate.since - timedelta(minutes=30)).isoformat(),
                    ),
                )
            else:
                # A confirmed event retains the pin until capture work owns it.
                pending = db.execute(
                    "SELECT 1 FROM outbox o JOIN events e ON e.id=o.id AND e.revision=o.revision WHERE e.mission=? AND e.leg=? AND o.acknowledged=0",
                    (observation.mission_id, observation.leg_id),
                ).fetchone()
                if not pending:
                    db.execute(
                        "DELETE FROM pins WHERE mission=? AND leg=?",
                        (observation.mission_id, observation.leg_id),
                    )
            return result

    def pin_start(self, mission_id: str, leg_id: str) -> datetime | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT start FROM pins WHERE mission=? AND leg=?", (mission_id, leg_id)
            ).fetchone()
            return datetime.fromisoformat(row[0]) if row else None

    def earliest_pin(self) -> datetime | None:
        with self.connect() as db:
            rows = db.execute("SELECT start FROM pins").fetchall()
            return min((datetime.fromisoformat(row[0]) for row in rows), default=None)

    @staticmethod
    def _validate_order(events):
        previous = None
        movement_events = [
            event
            for event in events
            if event.kind not in ("correction", "stop_classified")
        ]
        allowed = {
            None: {"off_blocks"},
            "off_blocks": {"takeoff"},
            "takeoff": {"landed"},
            "landed": {"on_blocks"},
            "on_blocks": {"off_blocks"},
        }
        for index, event in enumerate(movement_events):
            # Recovery can legitimately start history at landing. Let operators
            # correct it and supply the missing departure prefix incrementally;
            # each recovered segment can carry its own missing departure history.
            missing_departure = (
                event.kind == "landed"
                and event.evidence.get("missing_departure_history")
                and previous in (None, "off_blocks", "on_blocks")
            )
            following = (
                movement_events[index + 1] if index + 1 < len(movement_events) else None
            )
            missing_off_blocks = (
                event.kind == "takeoff"
                and previous in (None, "on_blocks")
                and following is not None
                and following.kind == "landed"
                and following.evidence.get("missing_departure_history")
            )
            if event.kind not in allowed[previous] and not (
                missing_departure or missing_off_blocks
            ):
                raise ValueError("Missing preceding event or invalid event ordering")
            previous = event.kind

    def record_manual_event(
        self,
        mission_id: str,
        leg_id: str,
        kind: str,
        occurred_at: datetime,
        reason: str,
        actor: str,
    ) -> FlightEvent:
        if not reason.strip():
            raise ValueError("A correction reason is required")
        event = FlightEvent(
            mission_id=mission_id,
            leg_id=leg_id,
            kind=kind,
            occurred_at=occurred_at,
            detected_at=datetime.now(timezone.utc),
            source="manual",
            confidence="operator_confirmed",
            evidence={"actor": actor, "reason": reason, "destination_complete": False},
        )
        if kind not in ("off_blocks", "takeoff", "landed", "on_blocks"):
            raise ValueError(
                "Use the dedicated stop classification or event correction operation"
            )
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            events = self._events(db, mission_id, leg_id) + [event]
            self._validate_order(sorted(events, key=lambda item: item.occurred_at))
            if self._state(db, mission_id, leg_id).destination_complete:
                raise ValueError(
                    "Leg arrival is already complete; correct existing events explicitly"
                )
            self._append(db, event)
            self._rebuild(db, mission_id, leg_id)
        return event

    def _rebuild(self, db, mission_id, leg_id):
        events = self._events(db, mission_id, leg_id)
        movement_events = [
            event
            for event in events
            if event.kind in ("off_blocks", "takeoff", "landed", "on_blocks")
        ]
        state = self._state(db, mission_id, leg_id)
        if movement_events:
            last = movement_events[-1]
            movement = {
                "off_blocks": "taxi_out",
                "takeoff": "airborne",
                "landed": "taxi_in",
                "on_blocks": "parked_at_stop",
            }[last.kind]
            # Backfilling departure history must not rewind a newer recovered
            # cruise observation to taxi. Corrections to arrival still rebuild
            # movement normally.
            keep_recovered_movement = (
                state.recovered_airborne
                and state.movement == "airborne"
                and last.kind in ("off_blocks", "takeoff")
                and state.last_observed_at is not None
                and last.occurred_at <= state.last_observed_at
            )
            if not keep_recovered_movement:
                state.movement = movement
            if last.kind == "takeoff":
                state.recovered_airborne = False
            classifications = {
                event.evidence.get("stop_id"): event.evidence.get("classification")
                for event in events
                if event.kind == "stop_classified"
            }
            state.destination_complete = last.kind == "on_blocks" and (
                classifications.get(
                    last.event_id,
                    (
                        "destination_complete"
                        if last.evidence.get("destination_complete", False)
                        else "intermediate"
                    ),
                )
                == "destination_complete"
            )
            if state.destination_complete:
                state.movement = "parked"
            state.uncertain = False
            state.candidate = None
            self._save_state(db, mission_id, leg_id, state)

    def correct_event(
        self,
        event_id: str,
        occurred_at: datetime,
        reason: str,
        actor: str,
        expected_revision: int,
        mission_id: str,
        leg_id: str,
    ) -> FlightEvent:
        if not reason.strip():
            raise ValueError("A correction reason is required")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT payload FROM events WHERE id=? ORDER BY revision DESC LIMIT 1",
                (event_id,),
            ).fetchone()
            if not row:
                raise ValueError("Event not found")
            current = FlightEvent.model_validate_json(row[0])
            if (current.mission_id, current.leg_id) != (mission_id, leg_id):
                raise ValueError("Event ownership mismatch")
            if current.revision != expected_revision:
                raise ValueError("Event revision conflict")
            revised = FlightEvent.model_validate(
                current.model_dump()
                | {
                    "occurred_at": occurred_at,
                    "detected_at": datetime.now(timezone.utc),
                    "source": "manual",
                    "confidence": "operator_confirmed",
                    "revision": current.revision + 1,
                    "evidence": current.evidence
                    | {
                        "actor": actor,
                        "reason": reason,
                        "prior_time": current.occurred_at.isoformat(),
                    },
                }
            )
            events = [
                revised if item.event_id == event_id else item
                for item in self._events(db, mission_id, leg_id)
            ]
            self._validate_order(sorted(events, key=lambda item: item.occurred_at))
            self._append(db, revised)
            self._rebuild(db, mission_id, leg_id)
            return revised

    def classify_stop(
        self,
        mission_id: str,
        leg_id: str,
        stop_id: str,
        classification: str,
        reason: str,
        actor: str,
    ) -> FlightEvent:
        if (
            classification not in ("intermediate", "destination_complete")
            or not reason.strip()
        ):
            raise ValueError("Valid classification and reason required")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            events = self._events(db, mission_id, leg_id)
            stop = next(
                (
                    event
                    for event in events
                    if event.event_id == stop_id and event.kind == "on_blocks"
                ),
                None,
            )
            if stop is None:
                raise ValueError("Stop ownership mismatch or not found")
            if any(
                event.kind in ("off_blocks", "takeoff")
                and event.occurred_at > stop.occurred_at
                for event in events
            ):
                raise ValueError("Cannot classify a stop before a later flight segment")
            event = FlightEvent(
                mission_id=mission_id,
                leg_id=leg_id,
                kind="stop_classified",
                occurred_at=stop.occurred_at,
                detected_at=datetime.now(timezone.utc),
                source="manual",
                confidence="operator_confirmed",
                evidence={
                    "stop_id": stop_id,
                    "classification": classification,
                    "reason": reason,
                    "actor": actor,
                },
            )
            self._append(db, event)
            self._rebuild(db, mission_id, leg_id)
            return event

    def pending_events(self) -> list[FlightEvent]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT e.payload FROM outbox o JOIN events e ON e.id=o.id AND e.revision=o.revision WHERE o.acknowledged=0 ORDER BY o.rowid"
            ).fetchall()
            return [FlightEvent.model_validate_json(row[0]) for row in rows]

    def acknowledge(self, event_id: str, revision: int) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE outbox SET acknowledged=1 WHERE id=? AND revision=?",
                (event_id, revision),
            )
