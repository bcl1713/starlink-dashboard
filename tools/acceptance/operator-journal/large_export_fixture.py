"""Synthetic-only dense archive input for the real mission preparation APIs."""

import hashlib
import json
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import psutil
from backend_fixture import app, main, root
from fastapi import HTTPException

from app.mission import storage
from app.services.flight_events.live_adapter import FlightEventRuntime
from app.services.telemetry_archive import stream_reader
from app.services.telemetry_archive.store import METRICS

MISSION = "synthetic-mission-a"
START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = START + timedelta(days=1)
COUNT = 300000
control = {"pause": False, "entered": False, "offset": 0, "limit": None}
original_samples = stream_reader.active_samples


def paused_samples(db, metadata, check):
    for sample in original_samples(db, metadata, check):
        if control["pause"]:
            control["entered"] = True
            while control["pause"]:
                check()
                time.sleep(0.01)
        yield sample


def rows(high_cardinality):
    for index in range(COUNT):
        stamp = START + timedelta(seconds=index // len(METRICS))
        metric = METRICS[index % len(METRICS)]
        labels = {
            "source": "prometheus_raw_scrape",
            "instance": "synthetic-export-441",
            "job": "synthetic",
        }
        if high_cardinality:
            labels["city"] = f"synthetic-label-{index}"
        if "ground_entry" in metric:
            labels.update(
                city=f"synthetic-pop-{index // 23400}",
                ip=f"198.51.100.{1 + index // 23400}",
                country="ZZ",
            )
            if index % 2:
                labels["source"] = "cached_last_known_proxy"
        value = (
            None
            if index % 101 == 0
            else 0.0 if index % 17 == 0 else float((index % 1000) - 100)
        )
        observed = None if index % 23 == 0 else stamp.isoformat()
        yield stamp.timestamp(), metric, json.dumps(
            labels, sort_keys=True
        ), value, "live", observed


def source_description(archive):
    digest = hashlib.sha256()
    with archive.ledger.connect() as db:
        budget = db.execute(
            "SELECT sum(512+length(metric)+length(labels)+coalesce(length(observed_at),0)) FROM samples WHERE ts>=? AND ts<=?",
            (START.timestamp(), END.timestamp()),
        ).fetchone()[0]
        count = 0
        for stamp, metric, labels, value, observed in db.execute(
            "SELECT ts,metric,labels,value,observed_at FROM samples WHERE ts>=? AND ts<=? ORDER BY ts,metric,labels",
            (START.timestamp(), END.timestamp()),
        ):
            item = {
                "timestamp": datetime.fromtimestamp(stamp, timezone.utc).isoformat(),
                "metric": metric,
                "labels": json.loads(labels),
                "value": value,
                "observed_at": observed,
            }
            digest.update((json.dumps(item, sort_keys=True) + "\n").encode())
            count += 1
    return {
        "rows": count,
        "digest": digest.hexdigest(),
        "old_input_accounting": budget,
        "archive_path": str(archive.ledger.path),
    }


def seed(high_cardinality=False):
    flight = app.state.flight_event_runtime
    mission = storage.load_mission_v2(MISSION)
    leg = mission.legs[0].id
    metadata = {
        "schema_version": 1,
        "mission_id": MISSION,
        "leg_id": leg,
        "revision": "synthetic-large",
        "state": "recording",
        "source_mode": "live",
        "complete": False,
        "start": START.isoformat(),
        "end": None,
        "available_until": END.isoformat(),
        "events": [],
        "samples": [],
        "gaps": [{"reason": "synthetic_acceptance_has_no_aircraft"}],
    }
    with flight.archive.ledger.connect() as db:
        db.execute("DELETE FROM samples")
        db.executemany(
            "INSERT INTO samples VALUES (?,?,?,?,?,?)", rows(high_cardinality)
        )
        db.execute(
            "INSERT OR REPLACE INTO captures VALUES (?,?,?,?)",
            (MISSION, leg, "synthetic-large", json.dumps(metadata)),
        )
        db.execute(
            "INSERT OR REPLACE INTO capture_heads VALUES (?,?,?)",
            (MISSION, leg, "synthetic-large"),
        )
    app.state.large_export_source = source_description(flight.archive)
    app.state.large_export_source.update(
        leg_id=leg, state="recording", high_cardinality=high_cardinality
    )


def seal():
    flight = app.state.flight_event_runtime
    archive, info = flight.archive, app.state.large_export_source
    body = root / "large-export" / "sealed-input.json"
    with archive.ledger.connect() as db:
        metadata = json.loads(
            db.execute(
                "SELECT payload FROM captures WHERE mission=? AND leg=?",
                (MISSION, info["leg_id"]),
            ).fetchone()[0]
        )
        metadata.update(state="sealed", complete=True, end=END.isoformat(), samples=[])
        with body.open("w") as output:
            prefix = json.dumps({k: v for k, v in metadata.items() if k != "samples"})
            output.write(prefix[:-1] + ', "samples":[')
            first = True
            for sample in original_samples(db, metadata, lambda: None):
                output.write(("" if first else ",") + json.dumps(sample))
                first = False
            output.write("]}")
        db.execute(
            "UPDATE captures SET payload=CAST(zeroblob(?) AS TEXT) WHERE mission=? AND leg=?",
            (body.stat().st_size, MISSION, info["leg_id"]),
        )
        rowid = db.execute(
            "SELECT rowid FROM captures WHERE mission=? AND leg=?",
            (MISSION, info["leg_id"]),
        ).fetchone()[0]
        with db.blobopen("captures", "payload", rowid) as target, body.open(
            "rb"
        ) as source:
            while block := source.read(65536):
                target.write(block)
        db.execute("DELETE FROM samples")
    body.unlink()
    info["state"] = "sealed"


def initialize():
    if os.getenv("OPERATOR_ACCEPTANCE_FIXTURE") != "synthetic-local-only":
        raise RuntimeError("Synthetic acceptance only")
    main.app.state.flight_event_runtime = FlightEventRuntime(root / "large-export")
    service = main.app.state.export_preparation_service
    # This probe isolates archive behavior; customer-PDF contracts have separate tests.
    service.enabled = False
    service.files.clock = lambda: time.time() + control["offset"]
    stream_reader.active_samples = paused_samples
    seed()


original_lifespan = app.router.lifespan_context


@asynccontextmanager
async def lifespan(application):
    async with original_lifespan(application):
        initialize()
        yield


app.router.lifespan_context = lifespan


@app.get("/api/_synthetic/large-export")
def status():
    service = app.state.export_preparation_service
    with service.cache.connection() as db:
        captures = db.execute(
            "SELECT count(*) FROM export_artifact_owners WHERE job IS NULL"
        ).fetchone()[0]
    return {
        **app.state.large_export_source,
        **control,
        "capture_owners": captures,
        "rss_bytes": psutil.Process().memory_info().rss,
    }


@app.post("/api/_synthetic/large-export")
def configure(body: dict):
    action = body.get("action")
    if action == "seal":
        seal()
    elif action == "recover":
        archive = app.state.flight_event_runtime.archive
        info = app.state.large_export_source
        with archive.ledger.connect() as db:
            rowid = db.execute(
                "SELECT c.rowid FROM captures c JOIN capture_heads h ON c.mission=h.mission AND c.leg=h.leg AND c.revision=h.revision WHERE h.mission=? AND h.leg=?",
                (MISSION, info["leg_id"]),
            ).fetchone()[0]
            metadata = stream_reader.read_capture(db, rowid, lambda: None)
            metadata.update(
                revision="synthetic-correction",
                state="recovering",
                complete=False,
                samples=[],
            )
            db.execute(
                "INSERT OR REPLACE INTO captures VALUES (?,?,?,?)",
                (MISSION, info["leg_id"], metadata["revision"], json.dumps(metadata)),
            )
            db.execute(
                "UPDATE capture_heads SET revision=? WHERE mission=? AND leg=?",
                (metadata["revision"], MISSION, info["leg_id"]),
            )
        info["state"] = "recovering"
    elif action == "seed":
        seed(high_cardinality=bool(body.get("high_cardinality")))
    elif action == "pause":
        control.update(pause=True, entered=False)
    elif action == "release":
        control.update(pause=False, entered=False, offset=0)
    elif action == "deadline":
        control["offset"] = 601
    elif action == "capacity":
        from app.mission.package import operations_archive

        operations_archive.MAX_ARCHIVE_FILES_BYTES = int(
            body.get("bytes", 256 * 1024 * 1024)
        )
    elif action == "write":
        started = time.monotonic()
        app.state.flight_event_runtime.archive.append(
            END + timedelta(seconds=1),
            METRICS[0],
            {"source": "synthetic_writer_probe"},
            1,
            "live",
        )
        return {"writer_seconds": time.monotonic() - started}
    else:
        raise HTTPException(422, "Unknown synthetic control")
    return status()
