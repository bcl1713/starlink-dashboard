"""Fixed clock/identity fixture from actual Stage 2 hooks and Stage 3A-shaped rows.

Process IDs/tokens are normalized explicitly for deterministic offline artifacts;
they are fixture identities, never host/runtime observations.
"""

import backend_probe as probe
from analyze import analyze
from evidence import BrowserProjection, canonical
from verify_evidence import verify_analysis


def fixture():
    probe.configure("C", "synthetic-test")
    with probe.operation("synthetic-test/p/doc/r1", "history"):
        for phase, stamp in [
            ("asgi.entry", 100),
            ("worker.dispatch", 110),
            ("worker.start", 120),
            ("worker.end", 150),
            ("worker.returned", 160),
            ("asgi.end", 180),
        ]:
            probe.mark(phase, at=(stamp, stamp // 10))
    events = probe.drain()
    for row in events:
        row.update(
            stream_id="fixture-backend",
            process_uuid="11111111-1111-4111-8111-111111111111",
            pid=77,
            tid=78,
            process_start_id="fixture-process-start",
            thread_start_id="fixture-thread-start",
            clock_id="fixture-backend-clock",
        )
    browser = BrowserProjection("C", "synthetic-test", "p")
    for seq, phase in enumerate(("app.request", "app.response", "query.success"), 1):
        events.append(
            browser.event(
                {
                    "run": "synthetic-test",
                    "stream": "synthetic-test/p/doc",
                    "clock": "browser/p/doc",
                    "seq": seq,
                    "monotonic_ms": seq,
                    "phase": phase,
                    "op": "synthetic-test/p/doc/r1",
                    "outcome": "ok",
                    "detail": {},
                }
            )
        )
    finals = [
        {"stream_id": "fixture-backend", "last_seq": 6, "dropped": 0, "complete": True},
        {
            "stream_id": "synthetic-test/p/doc",
            "last_seq": 3,
            "dropped": 0,
            "complete": True,
        },
    ]
    report = analyze(events, finals)
    verify_analysis(report, events)
    return {
        "events.jsonl": b"".join(canonical(row) + b"\n" for row in events),
        "summaries.json": canonical({"streams": finals}) + b"\n",
        "analysis.json": canonical(report) + b"\n",
    }
