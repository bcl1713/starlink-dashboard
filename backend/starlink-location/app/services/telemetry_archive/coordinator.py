"""Replay ledger events into idempotent capture work before acknowledging them."""

import hashlib
import json
import os
from datetime import datetime, timedelta
from uuid import uuid4

import httpx

from app.services.flight_events.store import FlightEventStore
from app.services.telemetry_archive.store import ArchiveStore


class CaptureCoordinator:
    def __init__(self, events: FlightEventStore, archive: ArchiveStore):
        self.events, self.archive = events, archive

    def recover(self, now: datetime):
        pending = self.events.pending_events()
        keys = {(event.mission_id, event.leg_id) for event in pending}
        keys.update(
            (capture["mission_id"], capture["leg_id"])
            for capture in self.archive.all_captures()
            if capture["state"] != "sealed"
        )
        for mission_id, leg_id in sorted(keys):
            self.refresh(mission_id, leg_id, now)
        self.publish_sealed()
        # Capture work committed first. A crash here replays it harmlessly.
        for event in pending:
            self.events.acknowledge(event.event_id, event.revision)
        return [self.archive.capture_summary(*key) for key in sorted(keys)]

    def refresh(self, mission_id: str, leg_id: str, now: datetime):
        events = self.events.events(mission_id, leg_id)
        departures = [event for event in events if event.kind == "off_blocks"]
        if not departures:
            return None
        start = departures[0].occurred_at - timedelta(minutes=30)
        classifications = {
            event.evidence.get("stop_id"): event.evidence.get("classification")
            for event in events
            if event.kind == "stop_classified"
        }
        destination_stops = [
            event
            for event in events
            if event.kind == "on_blocks"
            and classifications.get(
                event.event_id,
                (
                    "destination_complete"
                    if event.evidence.get("destination_complete")
                    else "intermediate"
                ),
            )
            == "destination_complete"
        ]
        stop = (
            min(destination_stops, key=lambda event: event.occurred_at)
            if destination_stops
            else None
        )
        end = stop.occurred_at + timedelta(minutes=30) if stop else None
        event_payload = [event.model_dump(mode="json") for event in events]
        revision = hashlib.sha256(
            json.dumps(event_payload, sort_keys=True).encode()
        ).hexdigest()
        with self.archive.ledger.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT payload FROM captures WHERE mission=? AND leg=? AND revision=?",
                (mission_id, leg_id, revision),
            ).fetchone()
            if existing and json.loads(existing[0])["state"] == "sealed":
                return json.loads(existing[0])
            until = min(now, end) if end else now
            points = db.execute(
                "SELECT DISTINCT ts FROM samples WHERE ts>=? AND ts<=? AND mode='live' ORDER BY ts",
                (start.timestamp(), until.timestamp()),
            ).fetchall()
            gaps = coverage_gaps(
                start,
                until,
                [
                    {
                        "timestamp": datetime.fromtimestamp(
                            row[0], now.tzinfo
                        ).isoformat()
                    }
                    for row in points
                ],
            )
            sealed = end is not None and now >= end and not gaps
            samples = self.archive._samples(db, start, until) if sealed else []
            payload = {
                "schema_version": 1,
                "mission_id": mission_id,
                "leg_id": leg_id,
                "revision": revision,
                "start": start.isoformat(),
                "end": end.isoformat() if end else None,
                "state": (
                    "sealed"
                    if sealed
                    else (
                        "recovering" if end is not None and now >= end else "recording"
                    )
                ),
                "source_mode": "live",
                "events": event_payload,
                "gaps": gaps,
                "complete": sealed and not gaps,
                "samples": samples if sealed else [],
                "available_until": until.isoformat(),
                "metric_provenance": "Prometheus raw scrape samples and accepted live source observations; timestamps retain source semantics",
            }
            db.execute(
                "INSERT OR REPLACE INTO captures VALUES (?, ?, ?, ?)",
                (mission_id, leg_id, revision, json.dumps(payload, sort_keys=True)),
            )
            db.execute(
                "INSERT OR REPLACE INTO capture_heads VALUES (?, ?, ?)",
                (mission_id, leg_id, revision),
            )
            db.execute(
                "DELETE FROM recovery_jobs WHERE mission=? AND leg=? AND revision!=?",
                (mission_id, leg_id, revision),
            )
            if gaps:
                db.execute(
                    "INSERT OR IGNORE INTO recovery_jobs(mission, leg, revision, cursor, until) VALUES (?, ?, ?, ?, ?)",
                    (
                        mission_id,
                        leg_id,
                        revision,
                        start.timestamp(),
                        until.timestamp(),
                    ),
                )
                db.execute(
                    "UPDATE recovery_jobs SET until=MAX(until, ?) WHERE mission=? AND leg=? AND revision=?",
                    (until.timestamp(), mission_id, leg_id, revision),
                )
            return payload

    def publish_sealed(self):
        from app.services.telemetry_archive.package import build_telemetry_package

        directory = self.archive.ledger.path.parent / "sealed"
        directory.mkdir(parents=True, exist_ok=True)
        for summary in self.archive.all_captures():
            if summary["state"] != "sealed":
                continue
            identity = json.dumps(
                [summary["mission_id"], summary["leg_id"], summary["revision"]]
            )
            target = directory / (
                hashlib.sha256(identity.encode()).hexdigest() + ".zip"
            )
            if target.exists():
                continue
            capture = self.archive.capture(
                summary["mission_id"], summary["leg_id"], summary["revision"]
            )
            temporary = directory / (target.name + "." + str(uuid4()) + ".tmp")
            try:
                with temporary.open("wb") as stream:
                    stream.write(
                        build_telemetry_package(
                            summary["mission_id"], [capture], allow_partial=True
                        )
                    )
                    stream.flush()
                    os.fsync(stream.fileno())
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)

    def backfill_one(self, reader, now: datetime):
        """One bounded query per tick; durable cursor and capped retry backoff."""
        with self.archive.ledger.connect() as db:
            row = db.execute(
                "SELECT mission, leg, revision, cursor, until, attempts FROM recovery_jobs WHERE cursor<=until AND retry_after<=? ORDER BY cursor LIMIT 1",
                (now.timestamp(),),
            ).fetchone()
        if row is None:
            return
        mission, leg, revision, cursor, until, attempts = row
        begin = datetime.fromtimestamp(cursor, now.tzinfo)
        end = datetime.fromtimestamp(min(cursor + 300, until), now.tzinfo)
        try:
            samples = reader.read(begin, end)
            self.archive.append_many(samples)
        except (httpx.HTTPError, ValueError, OSError) as error:
            with self.archive.ledger.connect() as db:
                db.execute(
                    "UPDATE recovery_jobs SET attempts=?, retry_after=?, error=? WHERE mission=? AND leg=? AND revision=?",
                    (
                        attempts + 1,
                        now.timestamp() + min(300, 2 ** min(attempts + 1, 8)),
                        type(error).__name__,
                        mission,
                        leg,
                        revision,
                    ),
                )
            return
        with self.archive.ledger.connect() as db:
            db.execute(
                "UPDATE recovery_jobs SET cursor=?, attempts=0, error=NULL WHERE mission=? AND leg=? AND revision=?",
                (
                    end.timestamp() if end.timestamp() < until else end.timestamp() + 1,
                    mission,
                    leg,
                    revision,
                ),
            )
        self.refresh(mission, leg, now)


def coverage_gaps(start, end, samples):
    points = sorted({datetime.fromisoformat(row["timestamp"]) for row in samples})
    if not points:
        return [
            {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "reason": "source_unavailable",
            }
        ]
    gaps = []
    previous = start
    for point in points + [end]:
        if (point - previous).total_seconds() > 10:
            gaps.append(
                {
                    "start": previous.isoformat(),
                    "end": point.isoformat(),
                    "reason": "missing_observations",
                }
            )
        previous = point
    return gaps
