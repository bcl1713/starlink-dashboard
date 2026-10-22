"""End-to-end offline qualification; no services, sockets, browsers or HTTP."""

import asyncio
import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from stage5_fixture import RUN, STATS, backend_fixture
from test_stage4 import COLLECTOR

import backend_probe as probe
import build
import workers
from analyze import analyze
from evidence import Evidence, canonical
from integration import Integration
from owner import Owner
from verify_evidence import validate_document, verify_analysis, verify_artifacts

PACKAGE = Path(__file__).resolve().parents[1]
FIXTURES = PACKAGE / "fixtures"


def replay(root, role, *, mutation=None):
    """Actual owner/sink/collector API with persisted browser records/artifacts."""
    owner = Owner(root, run=RUN, sources={"fixture": True, "pins": build.PINS})
    sink = Evidence(owner.root / "evidence", COLLECTOR, run=RUN)
    # Use verified production projection identities from the reviewed Stage 4 inventory.
    modules = json.loads(
        (PACKAGE / "evidence/stage4/derivative-identity.json").read_bytes()
    )["roles"][role]["projection_module_hashes"]
    adapter = Integration(sink, role=role, run=RUN, module_hashes=modules)
    try:
        rows = backend_fixture(role)
        stats = dict(STATS)
        if mutation == "missing":
            rows.pop(2)
        if mutation == "duplicate":
            rows.insert(2, copy.deepcopy(rows[1]))
        if mutation == "clock":
            rows[2]["mono_ns"] = "1"
        if mutation == "restart":
            rows[2]["process_start_id"] = "restarted"
        if mutation == "dropped":
            stats["dropped"] = 1
        adapter.backend(rows)
        adapter.finish_backend(stats)
        node = FIXTURES / "stage5-node"
        verify_artifacts(node)

        def load(ref):
            body = (node / ref["path"]).read_bytes()
            return body[:-1] if mutation == "partial" else body

        for raw in (node / "records.jsonl").read_text().splitlines():
            adapter.browser_record(json.loads(raw), load=load)
        adapter.finish_browser({"closed": True, "failed": False, "lost": 0})
        summary = sink.close()
        validate_document(summary, "summary")
        verify_artifacts(sink.root)
        events = [
            json.loads(line)
            for line in (sink.root / "integration.jsonl").read_text().splitlines()
        ]
        report = analyze(events, summary)
        verify_analysis(report, events)
        v1 = [
            json.loads(line)
            for line in (sink.root / "v1/events.jsonl").read_text().splitlines()
        ]
        for event in v1:
            COLLECTOR.model.validate(event)
        supplemental = COLLECTOR.analyze.analyze(v1)
        (root / "analysis.json").write_bytes(canonical(report) + b"\n")
        (root / "collector-analysis.json").write_bytes(canonical(supplemental) + b"\n")
        return summary, report, v1
    finally:
        if not sink.closed:
            sink.close()
        asyncio.run(owner.close())


class Stage5QualificationTests(unittest.TestCase):
    def test_persisted_backend_fixture_is_byte_identical(self):
        for role in ("A", "C"):
            self.assertEqual(
                (FIXTURES / "stage5" / (role + "-backend.jsonl")).read_bytes(),
                b"".join(canonical(r) + b"\n" for r in backend_fixture(role)),
            )

    def test_node_fixture_regeneration_is_byte_identical(self):
        with tempfile.TemporaryDirectory(prefix="perf391-stage5-node-") as tmp:
            target = Path(tmp) / "node"
            subprocess.run(
                ["node", "tests/stage5-node-fixture.mjs", str(target)],
                timeout=15,
                check=True,
                capture_output=True,
            )
            before = {
                p.relative_to(FIXTURES / "stage5-node"): p.read_bytes()
                for p in (FIXTURES / "stage5-node").rglob("*")
                if p.is_file()
            }
            after = {
                p.relative_to(target): p.read_bytes()
                for p in target.rglob("*")
                if p.is_file()
            }
            self.assertEqual(before, after)

    def test_full_pipeline_available_and_unavailable_boundaries_are_independent(self):
        for role in ("A", "C"):
            with self.subTest(role=role), tempfile.TemporaryDirectory(
                prefix="perf391-stage5-full-"
            ) as tmp:
                summary, report, v1 = replay(Path(tmp) / "run", role)
                self.assertTrue(summary["complete"])
                self.assertTrue(report["integrity"]["complete"])
                for name in (
                    "producer.collection",
                    "producer.execution",
                    "admission.hold",
                    "worker.queue",
                    "worker.execution",
                    "worker.delivery",
                    "polling.request_to_response",
                    "chart_input.commit",
                ):
                    self.assertTrue(report["boundaries"][name]["available"], name)
                self.assertEqual(
                    report["boundaries"]["producer.final_authority"]["available"],
                    role == "C",
                )
                self.assertEqual(
                    report["successful_publications"], 1 if role == "C" else None
                )
                self.assertFalse(
                    report["boundaries"]["presentation.capture"]["available"]
                )
                self.assertFalse(
                    report["unavailable"]["passive_http_capture"]["available"]
                )
                chart = next(row["data"] for row in v1 if row["kind"] == "chart")
                self.assertEqual(chart["traces"]["observed"], [2, 3, 4])
                self.assertIsNone(chart["paint_evidence"])
                self.assertIsNone(chart["visible_gaps"])
                supplemental = json.loads(
                    (Path(tmp) / "run/collector-analysis.json").read_bytes()
                )
                self.assertEqual(supplemental["acceptance"], "not_evaluated")
                self.assertEqual(supplemental["charts"][0]["classification"], "unknown")
                self.assertIn("paint", supplemental["charts"][0]["unavailable"])

    def test_corruptions_never_produce_verified_complete_durations(self):
        for mutation in (
            "missing",
            "duplicate",
            "clock",
            "restart",
            "dropped",
            "partial",
        ):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory(
                prefix="perf391-stage5-bad-"
            ) as tmp:
                if mutation == "partial":
                    with self.assertRaises(ValueError):
                        replay(Path(tmp) / "run", "C", mutation=mutation)
                else:
                    summary, report, _ = replay(
                        Path(tmp) / "run", "C", mutation=mutation
                    )
                    self.assertFalse(summary["complete"])
                    self.assertFalse(report["integrity"]["complete"])
                    self.assertTrue(all(d["ns"] is None for d in report["durations"]))
                manifest = json.loads((Path(tmp) / "run/manifest.json").read_bytes())
                self.assertEqual(
                    manifest["status"], "clean"
                )  # resource status, not evidence success

    def test_actual_guarded_tick_and_gate_events_survive_complete_pipeline(self):
        from test_admission import AdmissionTests
        from test_tick_boundaries import TickTests

        for role in ("A", "C"):
            _, tick = TickTests().execute(role, True, "normal")
            _, gate = AdmissionTests().exercise(role, True, "nested")
            for name, rows in (("tick", tick), ("gate", gate)):
                with tempfile.TemporaryDirectory(
                    prefix="perf391-stage5-real-hooks-"
                ) as tmp:
                    sink = Evidence(Path(tmp) / "evidence", COLLECTOR, run="offline")
                    adapter = Integration(sink, role=role, run="offline")
                    adapter.backend(rows)
                    adapter.finish_backend(STATS)
                    summary = sink.close()
                    events = [
                        json.loads(s)
                        for s in (sink.root / "integration.jsonl")
                        .read_text()
                        .splitlines()
                    ]
                    report = analyze(events, summary)
                    verify_analysis(report, events)
                    self.assertTrue(summary["complete"], (role, name))
                    boundary = (
                        "producer.collection" if name == "tick" else "admission.hold"
                    )
                    self.assertTrue(
                        report["boundaries"][boundary]["available"], (role, name)
                    )

    def test_cleanup_failure_stays_failed_even_with_valid_evidence(self):
        with tempfile.TemporaryDirectory(prefix="perf391-stage5-cleanup-") as tmp:
            owner = Owner(Path(tmp) / "owner", run=RUN, sources={})
            done = []
            owner.register_close(
                "fails", lambda: (_ for _ in ()).throw(OSError("fixture cleanup"))
            )
            owner.register_close("remaining", lambda: done.append(True))
            asyncio.run(owner.close())
            self.assertEqual(done, [True])
            self.assertEqual(owner.manifest["status"], "cleanup_failed")


class Stage5WorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_anyio_worker_events_through_owner_collector_analyzer(self):
        from starlette.concurrency import run_in_threadpool

        for role in ("A", "C"):
            with tempfile.TemporaryDirectory(prefix="perf391-stage5-worker-") as tmp:
                owner = Owner(Path(tmp) / "owner", run=RUN, sources={})
                sink = Evidence(owner.root / "evidence", COLLECTOR, run=RUN)
                owner.register_close("sink", sink.close)
                probe.configure(role, RUN)
                self.assertEqual(
                    await workers.await_pool(
                        "worker", "job", run_in_threadpool, lambda: 42
                    ),
                    42,
                )
                adapter = Integration(sink, role=role, run=RUN)
                adapter.backend(probe.drain())
                adapter.finish_backend(STATS)
                await owner.close()
                rows = [
                    json.loads(s)
                    for s in (sink.root / "integration.jsonl").read_text().splitlines()
                ]
                report = analyze(rows, sink.result)
                verify_analysis(report, rows)
                self.assertTrue(report["boundaries"]["worker.execution"]["available"])
                self.assertEqual(owner.manifest["status"], "clean")
