#!/usr/bin/env python3
"""Measure bounded delta reads, including store.connect, on synthetic history.

Run from backend/starlink-location with the configured Python dependencies.
The private store uses production migrations, indexes and command persistence.
No timing assertion: results describe this machine and warm filesystem caches.
"""

import argparse
import json
import os
import platform
import sqlite3
import statistics
import sys
import tempfile
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend/starlink-location"))

from app.operator.clock import SystemClock
from app.operator.commands import execute_in_transaction
from app.operator.models import Actor, CreateRecord, UpdateRecord
from app.operator.references import MissionReferences
from app.operator.service import OperatorService
from app.operator.settings import OperatorSettings
from app.operator.store import OperatorStore


def persist(connection, command, clock):
    return execute_in_transaction(
        connection,
        command,
        key=str(uuid4()),
        request_hash="synthetic-history-measurement",
        clock=clock,
        actor=Actor(),
    ).saved_records[0]


def measure(service, repeats):
    with service.store.connect() as connection:
        H = connection.execute(
            "SELECT coalesce(max(journal_seq),0) FROM revisions"
        ).fetchone()[0]
    statements = []
    with service.store.connect() as connection:
        connection.set_trace_callback(statements.append)
        from app.operator.queries import changes

        changes(
            connection,
            clock=service.clock,
            mission_id="mission-a",
            source={},
            after_seq=max(0, H - 100),
        )
    plans = []
    with service.store.connect() as connection:
        for statement in statements:
            if statement.startswith(("SELECT", "WITH")):
                plans.append(
                    {
                        "sql": statement,
                        "plan": connection.execute(
                            "EXPLAIN QUERY PLAN " + statement
                        ).fetchall(),
                    }
                )
    timings = {}
    for name, after in (("idle", H), ("recent_100_revisions", max(0, H - 100))):
        values = []
        for _ in range(repeats):
            started = time.perf_counter()
            page = service.changes("mission-a", source={}, after_seq=after)
            assert page.H == H
            if name == "idle":
                assert not page.items
            values.append((time.perf_counter() - started) * 1000)
        ordered = sorted(values)
        timings[name + "_ms"] = {
            "min": min(values),
            "median": statistics.median(values),
            "p95": ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))],
            "max": max(values),
        }
    return {"revisions": H, "samples": repeats, **timings, "query_plans": plans}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--revisions", type=int, default=100000)
    parser.add_argument("--samples", type=int, default=30)
    args = parser.parse_args()
    if args.revisions < 10000 or args.revisions % 10 or args.samples < 2:
        parser.error("revisions must be a multiple of 10 >=10000; samples >=2")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    ownership = {
        "pid": os.getpid(),
        "pgid": os.getpgrp(),
        "command": sys.argv,
        "temporaryPath": None,
    }
    owner_file = args.output.with_suffix(".ownership.json")
    owner_file.write_text(json.dumps(ownership, indent=2))
    clock = SystemClock()
    report = {
        "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version,
        "scope": "service.changes including production store.connect admission, connection, transaction, final max(recorded_at), commit and close; no HTTP/projection serialization; warm OS cache",
        "samples": [],
    }
    try:
        with tempfile.TemporaryDirectory(prefix="issue-430-history-") as temporary:
            ownership["temporaryPath"] = temporary
            owner_file.write_text(json.dumps(ownership, indent=2))
            store = OperatorStore.open(
                OperatorSettings(root=Path(temporary)), initialize=True, clock=clock
            )
            try:
                service = OperatorService(
                    store, clock=clock, actor=Actor(), references=MissionReferences()
                )
                report["samples"].append(measure(service, args.samples))
                for boundary in sorted({10000, args.revisions}):
                    start = report["samples"][-1]["revisions"]
                    # Ten accepted immutable revisions per record, 10% in A.
                    # Persist real command receipts and pointer transitions in a
                    # bulk transaction; no dropped indexes or disabled triggers.
                    with store.connect(write=True) as connection:
                        for index in range(start // 10, boundary // 10):
                            body = {
                                "record_type": "journal_entry",
                                "mission_id": (
                                    "mission-a" if index % 10 == 0 else "mission-b"
                                ),
                                "scope": "mission",
                                "time": {},
                                "payload": {
                                    "entry_type": "note",
                                    "title": f"Synthetic {index}",
                                    "note": "Accumulated-history measurement",
                                },
                            }
                            row = persist(
                                connection, CreateRecord.model_validate(body), clock
                            )
                            for version in range(1, 10):
                                row = persist(
                                    connection,
                                    UpdateRecord.model_validate(
                                        {
                                            **body,
                                            "record_id": row.record_id,
                                            "expected_version": version,
                                            "audit_note": f"Synthetic revision {version+1}",
                                        }
                                    ),
                                    clock,
                                )
                    sample = measure(service, args.samples)
                    sample["database_bytes"] = (
                        store.settings.database_path.stat().st_size
                    )
                    sample["current_records"] = boundary // 10
                    report["samples"].append(sample)
            finally:
                store.close()
    finally:
        ownership["temporaryPathRemoved"] = (
            not ownership["temporaryPath"]
            or not Path(ownership["temporaryPath"]).exists()
        )
        owner_file.write_text(json.dumps(ownership, indent=2))
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
