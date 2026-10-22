"""Fixed timestamps/identities emitted by the real Stage 2 probe entrypoint.

These are deterministic event inputs; source-slice parity and actual AnyIO/gate
integration are independently exercised by the existing suite and Stage 5 tests.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend_probe as probe
from evidence import canonical

RUN = "synthetic-stage5"
STATS = {"buffered": 0, "dropped": 0, "invalid": 0, "failures": 0}


def backend_fixture(role):
    probe.configure(role, RUN)
    operations = [
        (
            "producer",
            "tick",
            [
                "producer.dispatch",
                "producer.start",
                "collection.enter",
                "collection.return",
                "producer.collected",
            ]
            + (
                [
                    "source.final.begin",
                    "source.final.end",
                    "publication.attempt",
                    "publication.result",
                    "producer.published",
                ]
                if role == "C"
                else ["metrics.inplace.begin", "metrics.inplace.end"]
            )
            + ["producer.end", "producer.returned"],
        ),
        (
            RUN + "/p/doc/r1",
            "history",
            [
                "asgi.entry",
                "repo.wait",
                "repo.local_grant",
                "repo.acquired",
                "repo.released",
                "worker.dispatch",
                "worker.start",
                "worker.end",
                "worker.returned",
                "history.begin",
                "history.end",
                "asgi.end",
            ],
        ),
    ]
    stamp = 100
    for op, kind, phases in operations:
        with probe.operation(op, kind):
            for phase in phases:
                identity = (
                    {"cas_success": True, "publication_kind": "ready"}
                    if phase in ("publication.result", "producer.published")
                    else None
                )
                probe.mark(phase, identity=identity, at=(stamp, stamp // 10))
                stamp += 10
    rows = probe.drain()
    for row in rows:
        row.update(
            stream_id="fixture-backend",
            process_uuid="11111111-1111-4111-8111-111111111111",
            pid=77,
            tid=78,
            process_start_id="fixture-process-start",
            thread_start_id="fixture-thread-start",
            clock_id="fixture-backend-clock",
        )
    return rows


def write_backend(root, role):
    rows = backend_fixture(role)
    (root / (role + "-backend.jsonl")).write_bytes(
        b"".join(canonical(r) + b"\n" for r in rows)
    )
    (root / "backend-stats.json").write_bytes(canonical(STATS) + b"\n")
    return rows
