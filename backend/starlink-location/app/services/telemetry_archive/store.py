"""Transactional raw observations and capture revisions on a persistent volume."""

import json
from datetime import datetime, timedelta, timezone
from math import isfinite
from pathlib import Path

from app.services.flight_events.store import FlightEventStore

METRICS = (
    "starlink_dish_latitude_degrees",
    "starlink_dish_longitude_degrees",
    "starlink_dish_altitude_feet",
    "starlink_dish_speed_knots",
    "starlink_dish_heading_degrees",
    "starlink_network_latency_ms_current",
    "starlink_network_throughput_down_mbps_current",
    "starlink_network_throughput_up_mbps_current",
    "starlink_network_packet_loss_percent",
    "starlink_dish_obstruction_percent",
    "starlink_signal_quality_percent",
    "starlink_ground_entry_point_info",
    "starlink_ground_entry_point_location",
)
LABELS = {
    "public_ip",
    "ip",
    "name",
    "city",
    "country",
    "country_code",
    "region",
    "display",
    "latitude",
    "longitude",
    "lat",
    "lon",
    "location",
    "source",
    "ground_entry_point",
    "pop",
    "instance",
    "job",
    "geohash",
}


class ArchiveStore:
    def __init__(self, path: Path):
        self.ledger = FlightEventStore(path)
        with self.ledger.connect() as db:
            # Pinned export readers must not prevent live recording commits.
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS samples (
                    ts REAL, metric TEXT, labels TEXT, value REAL, mode TEXT,
                    observed_at TEXT, PRIMARY KEY(ts, metric, labels, mode));
                CREATE TABLE IF NOT EXISTS captures (
                    mission TEXT, leg TEXT, revision TEXT, payload TEXT,
                    PRIMARY KEY(mission, leg, revision));
                CREATE TABLE IF NOT EXISTS capture_heads (
                    mission TEXT, leg TEXT, revision TEXT, PRIMARY KEY(mission, leg));
                CREATE TABLE IF NOT EXISTS raw_windows (
                    mission TEXT, leg TEXT, revision TEXT, start REAL, end REAL,
                    status TEXT DEFAULT 'pending', attempts INTEGER DEFAULT 0,
                    next_retry REAL DEFAULT 0, lease_until REAL DEFAULT 0, error TEXT,
                    PRIMARY KEY(mission, leg, revision, start));
                CREATE TABLE IF NOT EXISTS recovery_jobs (
                    mission TEXT, leg TEXT, revision TEXT, cursor REAL, until REAL,
                    retry_after REAL DEFAULT 0, attempts INTEGER DEFAULT 0, error TEXT,
                    PRIMARY KEY(mission, leg, revision));
                CREATE TABLE IF NOT EXISTS consumed_events (
                    id TEXT, revision INTEGER, PRIMARY KEY(id, revision));
            """)

    def append(
        self,
        timestamp: datetime,
        metric: str,
        labels: dict,
        value: float | None,
        mode: str,
        observed_at: datetime | None = None,
    ):
        self.append_many([(timestamp, metric, labels, value, mode, observed_at)])

    def append_many(self, rows):
        normalized = []
        for timestamp, metric, labels, value, mode, observed_at in rows:
            if metric not in METRICS or mode != "live" or timestamp.utcoffset() is None:
                continue
            numeric = (
                float(value) if value is not None and isfinite(float(value)) else None
            )
            safe_labels = {
                key: str(val) for key, val in labels.items() if key in LABELS
            }
            normalized.append(
                (
                    timestamp.timestamp(),
                    metric,
                    json.dumps(safe_labels, sort_keys=True),
                    numeric,
                    mode,
                    observed_at.isoformat() if observed_at else None,
                )
            )
        with self.ledger.connect() as db:
            db.executemany(
                "INSERT OR IGNORE INTO samples VALUES (?, ?, ?, ?, ?, ?)", normalized
            )

    def samples(self, start: datetime, end: datetime, *, budget=None) -> list[dict]:
        with self.ledger.connect() as db:
            return self._samples(db, start, end, budget=budget)

    def _samples(self, db, start, end, *, budget=None):
        rows = db.execute(
            "SELECT ts, metric, labels, value, observed_at FROM samples WHERE ts>=? AND ts<=? AND mode='live' ORDER BY ts, metric, labels",
            (start.timestamp(), end.timestamp()),
        )
        result = []
        for row in rows:
            if budget is not None:
                budget[0] -= (
                    512
                    + len(row[1].encode("utf-8"))
                    + len(row[2].encode("utf-8"))
                    + len((row[4] or "").encode("utf-8"))
                )
                if budget[0] < 0:
                    raise RuntimeError("Telemetry archive input size limit exceeded")
            result.append(
                {
                    "timestamp": datetime.fromtimestamp(
                        row[0], timezone.utc
                    ).isoformat(),
                    "metric": row[1],
                    "labels": json.loads(row[2]),
                    "value": row[3],
                    "observed_at": row[4],
                }
            )
        return result

    def capture(
        self, mission_id: str, leg_id: str, revision: str | None = None, *, budget=None
    ) -> dict | None:
        with self.ledger.connect() as db:
            if revision is None:
                row = db.execute(
                    "SELECT revision FROM capture_heads WHERE mission=? AND leg=?",
                    (mission_id, leg_id),
                ).fetchone()
                if not row:
                    return None
                revision = row[0]
            if budget is not None:
                size = db.execute(
                    "SELECT length(CAST(payload AS BLOB)) FROM captures WHERE mission=? AND leg=? AND revision=?",
                    (mission_id, leg_id, revision),
                ).fetchone()
                budget[0] -= size[0] if size else 0
                if budget[0] < 0:
                    raise RuntimeError("Telemetry archive input size limit exceeded")
            row = db.execute(
                "SELECT payload FROM captures WHERE mission=? AND leg=? AND revision=?",
                (mission_id, leg_id, revision),
            ).fetchone()
            return json.loads(row[0]) if row else None

    def preserved(self, mission_id: str, leg_id: str):
        """Sealed revisions are the durable source after rolling cleanup."""
        with self.ledger.connect() as db:
            rows = db.execute(
                "SELECT payload FROM captures WHERE mission=? AND leg=? AND json_extract(payload, '$.state')='sealed'",
                (mission_id, leg_id),
            ).fetchall()
        samples, coverage = {}, []
        for row in rows:
            capture = json.loads(row[0])
            for sample in capture.get("samples", []):
                key = (
                    sample["timestamp"],
                    sample["metric"],
                    json.dumps(sample["labels"], sort_keys=True),
                )
                samples[key] = sample
            coverage.extend(capture.get("raw_coverage", []))
        return list(samples.values()), coverage

    def capture_summary(self, mission_id: str, leg_id: str):
        with self.ledger.connect() as db:
            row = db.execute(
                "SELECT json_remove(c.payload, '$.samples') FROM captures c JOIN capture_heads h ON c.mission=h.mission AND c.leg=h.leg AND c.revision=h.revision WHERE c.mission=? AND c.leg=?",
                (mission_id, leg_id),
            ).fetchone()
            return json.loads(row[0]) if row else None

    def all_captures(self):
        with self.ledger.connect() as db:
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT json_remove(c.payload, '$.samples') FROM captures c JOIN capture_heads h ON c.mission=h.mission AND c.leg=h.leg AND c.revision=h.revision"
                )
            ]

    def gc(self, now: datetime, pin_start: datetime | None):
        cutoff = now - timedelta(minutes=35)
        if pin_start is not None:
            cutoff = min(cutoff, pin_start)
        # Active captures pin their ranges; sealed revisions contain immutable
        # sample snapshots and no longer depend on rolling source rows.
        for capture in self.all_captures():
            if capture["state"] != "sealed":
                cutoff = min(cutoff, datetime.fromisoformat(capture["start"]))
        with self.ledger.connect() as db:
            db.execute("DELETE FROM samples WHERE ts<?", (cutoff.timestamp(),))
