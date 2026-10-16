"""Idempotent capture snapshots with independent, bounded raw extraction."""

import hashlib
import json
from datetime import datetime, timedelta

from app.services.flight_events.store import FlightEventStore
from app.services.telemetry_archive.coverage import (
    coverage_gaps,
    iso,
    merge_ranges,
    uncovered,
)
from app.services.telemetry_archive.store import METRICS, ArchiveStore


class CaptureCoordinator:
    def __init__(self, events: FlightEventStore, archive: ArchiveStore):
        self.events, self.archive = events, archive
        self.max_retries = 12

    def recover(self, now: datetime):
        pending = self.events.pending_events()
        keys = {(event.mission_id, event.leg_id) for event in pending}
        keys.update(
            (item["mission_id"], item["leg_id"])
            for item in self.archive.all_captures()
            if item["state"] != "sealed"
        )
        for key in sorted(keys):
            self.refresh(*key, now)
        self.publish_sealed()
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
        stops = [
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
        stop = min(stops, key=lambda event: event.occurred_at) if stops else None
        end = stop.occurred_at + timedelta(minutes=30) if stop else None
        event_payload = [event.model_dump(mode="json") for event in events]
        revision = hashlib.sha256(
            json.dumps(event_payload, sort_keys=True).encode()
        ).hexdigest()
        current = self.archive.capture_summary(mission_id, leg_id)
        if current and current["revision"] == revision and current["state"] == "sealed":
            return current
        preserved, inherited = self.archive.preserved(mission_id, leg_id)
        inherited_ranges = [
            (
                datetime.fromisoformat(span["start"]).timestamp(),
                datetime.fromisoformat(span["end"]).timestamp(),
            )
            for span in inherited
        ]
        until = min(now, end) if end else now
        # Leave enough time for the final raw scrape to arrive. The capture's
        # declared end remains fixed; only confirmation is delayed.
        horizon = min(until, now - timedelta(seconds=10))
        with self.archive.ledger.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "DELETE FROM raw_windows WHERE mission=? AND leg=? AND revision!=?",
                (mission_id, leg_id, revision),
            )
            windows = db.execute(
                "SELECT start, end, status, attempts FROM raw_windows WHERE mission=? AND leg=? AND revision=? ORDER BY start",
                (mission_id, leg_id, revision),
            ).fetchall()
            scheduled = inherited_ranges + [(row[0], row[1]) for row in windows]
            for left, right in uncovered(
                start.timestamp(), horizon.timestamp(), scheduled
            ):
                while left < right:
                    boundary = min(left + 300, right)
                    db.execute(
                        "INSERT OR IGNORE INTO raw_windows(mission, leg, revision, start, end) VALUES (?, ?, ?, ?, ?)",
                        (mission_id, leg_id, revision, left, boundary),
                    )
                    left = boundary
            windows = db.execute(
                "SELECT start, end, status, attempts FROM raw_windows WHERE mission=? AND leg=? AND revision=? ORDER BY start",
                (mission_id, leg_id, revision),
            ).fetchall()
            done_ranges = inherited_ranges + [
                (row[0], row[1]) for row in windows if row[2] == "done"
            ]
            terminal = horizon >= until and all(
                row[2] in ("done", "failed") for row in windows
            )
            sealed = end is not None and now >= end + timedelta(seconds=10) and terminal
            # Do not treat live rows as proof that all raw metric series have
            # been extracted. Native and raw collection coverage are separate.
            rolling = self.archive._samples(db, start, until) if sealed else []
            retained = [
                sample
                for sample in preserved
                if start <= datetime.fromisoformat(sample["timestamp"]) <= until
            ]
            if sealed:
                combined = {
                    (
                        sample["timestamp"],
                        sample["metric"],
                        json.dumps(sample["labels"], sort_keys=True),
                    ): sample
                    for sample in retained + rolling
                }
                samples = [combined[key] for key in sorted(combined)]
                gaps = coverage_gaps(start, until, samples)
            else:
                samples = []
                points = db.execute(
                    "SELECT DISTINCT ts FROM samples WHERE ts>=? AND ts<=? ORDER BY ts",
                    (start.timestamp(), until.timestamp()),
                ).fetchall()
                gaps = coverage_gaps(
                    start,
                    until,
                    retained
                    + [
                        {
                            "timestamp": datetime.fromtimestamp(
                                row[0], now.tzinfo
                            ).isoformat()
                        }
                        for row in points
                    ],
                )
            for left, right in uncovered(
                start.timestamp(), until.timestamp(), done_ranges
            ):
                exhausted = any(
                    row[2] == "failed" and row[0] < right and row[1] > left
                    for row in windows
                )
                gaps.append(
                    {
                        "start": iso(left, now),
                        "end": iso(right, now),
                        "reason": (
                            "raw_recovery_exhausted"
                            if exhausted
                            else "raw_extraction_pending"
                        ),
                    }
                )
            present = {
                sample["metric"]
                for sample in samples
                if sample.get("value") is not None
            }
            missing_metrics = (
                [metric for metric in METRICS if metric not in present]
                if sealed
                else []
            )
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
                    else ("recovering" if end and now >= end else "recording")
                ),
                "source_mode": "live",
                "events": event_payload,
                "gaps": gaps,
                "complete": sealed and not gaps and not missing_metrics,
                "samples": samples,
                "available_until": until.isoformat(),
                "metric_allowlist": list(METRICS),
                "missing_metrics": missing_metrics,
                "raw_coverage": [
                    {"start": iso(left, now), "end": iso(right, now)}
                    for left, right in merge_ranges(done_ranges)
                    if right >= start.timestamp() and left <= until.timestamp()
                ],
                "metric_provenance": "Raw Prometheus scrape samples and accepted live observations retain distinct source labels and timestamp semantics",
            }
            db.execute(
                "INSERT OR REPLACE INTO captures VALUES (?, ?, ?, ?)",
                (mission_id, leg_id, revision, json.dumps(payload, sort_keys=True)),
            )
            db.execute(
                "INSERT OR REPLACE INTO capture_heads VALUES (?, ?, ?)",
                (mission_id, leg_id, revision),
            )
            return payload

    def backfill_one(self, reader, now: datetime):
        from app.services.telemetry_archive.recovery import backfill_one

        backfill_one(self, reader, now)

    def publish_sealed(self):
        from app.services.telemetry_archive.publication import publish_sealed

        publish_sealed(self.archive)
