"""Leased raw extraction windows retry incomplete responses before finalizing."""

from datetime import datetime

import httpx

from app.services.telemetry_archive.coverage import coverage_gaps


def backfill_one(coordinator, reader, now: datetime):
    with coordinator.archive.ledger.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT mission, leg, revision, start, end, attempts FROM raw_windows WHERE status IN ('pending','retry') AND next_retry<=? AND lease_until<=? ORDER BY start LIMIT 1",
            (now.timestamp(), now.timestamp()),
        ).fetchone()
        if row:
            db.execute(
                "UPDATE raw_windows SET lease_until=? WHERE mission=? AND leg=? AND revision=? AND start=?",
                (now.timestamp() + 30, row[0], row[1], row[2], row[3]),
            )
    if row is None:
        return
    mission, leg, revision, left, right, attempts = row
    begin, end = datetime.fromtimestamp(left, now.tzinfo), datetime.fromtimestamp(
        right, now.tzinfo
    )
    error = None
    try:
        batch = reader.read(begin, end)
        coordinator.archive.append_many(batch)
        raw_points = [
            {"timestamp": item[0].isoformat()}
            for item in batch
            if begin <= item[0] <= end
        ]
        if coverage_gaps(begin, end, raw_points):
            error = "incomplete_raw_interval"
    except (httpx.HTTPError, ValueError, OSError) as failure:
        error = type(failure).__name__
    attempts += 1
    status = (
        "done"
        if error is None
        else ("failed" if attempts >= coordinator.max_retries else "retry")
    )
    with coordinator.archive.ledger.connect() as db:
        db.execute(
            "UPDATE raw_windows SET status=?, attempts=?, next_retry=?, lease_until=0, error=? WHERE mission=? AND leg=? AND revision=? AND start=?",
            (
                status,
                attempts,
                now.timestamp() + min(300, 2 ** min(attempts, 8)),
                error,
                mission,
                leg,
                revision,
                left,
            ),
        )
    coordinator.refresh(mission, leg, now)
