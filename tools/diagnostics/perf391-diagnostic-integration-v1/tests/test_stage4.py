"""Stage 4 offline contracts: false completeness, identity reuse and unsafe cleanup."""

import asyncio
import copy
import errno
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import backend_probe as probe
import contract
from analyze import analyze
from collector import prepare_collector
from evidence import BrowserProjection, Evidence
from host import alignment, anchor, counter_delta, sample
from owner import Owner

_TEMP = tempfile.TemporaryDirectory(prefix="perf391-stage4-collector-")
import atexit

atexit.register(_TEMP.cleanup)
COLLECTOR = prepare_collector(Path(_TEMP.name) / "collector", PACKAGE.parents[2])


def backend(phases, *, kind="history", op="synthetic-test/p/doc/r1", role="C"):
    probe.configure(role, "synthetic-test")
    with probe.operation(op, kind):
        for i, phase in enumerate(phases):
            probe.mark(phase, at=(100 + i * 10, 30 + i * 2))
    return probe.drain()


def summaries(rows):
    return [
        {
            "stream_id": stream,
            "last_seq": max(r["seq"] for r in rows if r["stream_id"] == stream),
            "dropped": 0,
            "complete": True,
        }
        for stream in sorted({r["stream_id"] for r in rows})
    ]


class AnalyzerTests(unittest.TestCase):
    def test_every_claim_has_unique_complete_same_clock_boundaries(self):
        rows = backend(
            ["worker.dispatch", "worker.start", "worker.end", "worker.returned"]
        )
        report = analyze(rows, summaries(rows))
        self.assertTrue(report["integrity"]["complete"])
        claims = [v for v in report["durations"] if v["ns"] is not None]
        self.assertEqual([c["ns"] for c in claims], [10, 10, 10])
        for c in claims:
            self.assertEqual(len(c["events"]), 2)
            self.assertEqual(c["events"][0]["clock_id"], c["events"][1]["clock_id"])
        for mutation in ["missing", "duplicate", "clock", "restart", "thread"]:
            broken = copy.deepcopy(rows)
            if mutation == "missing":
                broken.pop(2)
            if mutation == "duplicate":
                broken.insert(2, copy.deepcopy(broken[1]))
            if mutation == "clock":
                broken[2]["clock_id"] = "other"
            if mutation == "restart":
                broken[2]["process_start_id"] = "reused-pid"
            if mutation == "thread":
                broken[2]["thread_start_id"] = "reused-tid"
            result = analyze(broken, summaries(broken))
            self.assertTrue(any(d["ns"] is None for d in result["durations"]))
            self.assertFalse(result["integrity"]["complete"])

    def test_missing_summaries_and_failed_workers_do_not_become_zero(self):
        rows = backend(
            ["worker.dispatch", "worker.start", "worker.end", "worker.returned"]
        )
        rows[2]["outcome"] = "error"
        rows[3]["outcome"] = "error"
        report = analyze(rows, [])
        self.assertFalse(report["integrity"]["complete"])
        self.assertTrue(all(d["ns"] is None for d in report["durations"]))
        self.assertEqual(report["unavailable"]["axios_parse_start"]["available"], False)

    def test_a_publication_unavailable_and_c_cas_lost_is_no_success(self):
        for role in ("A", "C"):
            rows = backend(["producer.start", "producer.end"], kind="tick", role=role)
            report = analyze(rows, summaries(rows))
            self.assertIsNone(report["successful_publications"])
            self.assertIsNone(
                next(
                    d
                    for d in report["durations"]
                    if d["boundary"] == "producer.publication"
                )["ns"]
            )

    def test_explicit_request_join_survives_clock_offset_but_never_subtracts_it(self):
        rows = backend(["asgi.entry", "asgi.end"])
        browser = BrowserProjection("C", "synthetic-test", "p")
        raw = {
            "run": "synthetic-test",
            "stream": "synthetic-test/p/doc",
            "clock": "browser/p/doc",
            "seq": 1,
            "monotonic_ms": 99999,
            "phase": "app.request",
            "op": rows[0]["op_id"],
            "outcome": "ok",
            "detail": {},
        }
        event = browser.event(raw)
        report = analyze([*rows, event], summaries([*rows, event]))
        self.assertEqual(report["request_joins"][0]["state"], "joined")
        self.assertFalse(
            any(
                d["boundary"] == "cross_clock_one_way" and d["ns"] is not None
                for d in report["durations"]
            )
        )
        raw.update(seq=2, phase="app.response", op="different")
        other = browser.event(raw)
        report = analyze([*rows, event, other], summaries([*rows, event, other]))
        self.assertEqual(
            {j["state"] for j in report["request_joins"]}, {"joined", "unavailable"}
        )


class HostTests(unittest.TestCase):
    def test_fixed_proc_cgroup_and_inaccessible_files_preserve_identity(self):
        with tempfile.TemporaryDirectory(prefix="perf391-stage4-proc-") as tmp:
            root = Path(tmp)
            (root / "7/task/8").mkdir(parents=True)
            (root / "sys/kernel/random").mkdir(parents=True)
            stat = "7 (fixture ) name) S " + " ".join(["0"] * 18 + ["123"] + ["0"] * 30)
            (root / "7/stat").write_text(stat)
            (root / "7/task/8/stat").write_text(stat.replace("7 (", "8 ("))
            (root / "7/schedstat").write_text("100 20 3")
            (root / "7/task/8/schedstat").write_text("90 10 2")
            (root / "sys/kernel/random/boot_id").write_text("boot1")
            group = root / "cg"
            group.mkdir()
            (group / "cpu.stat").write_text(
                "usage_usec 12\nnr_throttled 2\nthrottled_usec 8\n"
            )
            result = sample(
                COLLECTOR,
                proc_root=root,
                pids=[7],
                cgroups=[group],
                now=iter([10, 20]).__next__,
            )
            self.assertEqual(result["processes"][0]["start_id"], "123")
            self.assertEqual(result["processes"][0]["threads"][0]["start_id"], "123")
            self.assertEqual(
                result["files"][str(root / "7/schedstat")]["value"], "100 20 3"
            )
            self.assertIsNone(result["files"][str(group / "cpu.max")]["value"])
            self.assertEqual(result["bracket_ns"], ["10", "20"])

    def test_counter_reset_pid_reuse_clock_and_missing_are_unavailable(self):
        a = {"clock_id": "host", "identity": "pid7/start1", "epoch": "cg1", "value": 10}
        self.assertEqual(counter_delta(a, {**a, "value": 14})["value"], 4)
        for change in [
            {"value": 1},
            {"identity": "pid7/start2"},
            {"epoch": "cg2"},
            {"clock_id": "backend"},
            {"value": None},
        ]:
            self.assertIsNone(counter_delta(a, {**a, **change})["value"])

    def test_bracketed_wall_clock_step_only_invalidates_approximate_alignment(self):
        one = anchor("host", now=iter([100, 120]).__next__, utc=lambda: 1000)
        two = anchor("host", now=iter([200, 220]).__next__, utc=lambda: 5000)
        self.assertEqual(one["uncertainty_ns"], "20")
        self.assertFalse(alignment(one, two)["available"])

    def test_host_file_thread_and_total_sample_bounds(self):
        with tempfile.TemporaryDirectory(prefix="perf391-stage4-cap-") as tmp:
            root = Path(tmp)
            (root / "7/task").mkdir(parents=True)
            for i in range(3):
                (root / f"7/task/{i}").mkdir()
            (root / "7/io").write_bytes(b"x" * 65537)
            result = sample(COLLECTOR, proc_root=root, pids=[7], max_threads=2)
            self.assertEqual(
                result["files"][str(root / "7/io")]["reason"], "file_limit"
            )
            self.assertEqual(
                result["files"][str(root / "7/task")]["reason"], "thread_limit"
            )
        with self.assertRaises(ValueError):
            sample(COLLECTOR, pids=range(9))


class EvidenceTests(unittest.TestCase):
    def test_real_backend_and_browser_events_project_through_pinned_collector(self):
        with tempfile.TemporaryDirectory(prefix="perf391-stage4-evidence-") as tmp:
            sink = Evidence(Path(tmp) / "run", COLLECTOR, run="synthetic-test")
            rows = backend(
                ["worker.dispatch", "worker.start", "worker.end", "worker.returned"]
            )
            for row in rows:
                self.assertTrue(sink.accept(row))
            sink.summary(rows[0]["stream_id"], last_seq=4, dropped=0, complete=True)
            result = sink.close()
            self.assertTrue(result["complete"])
            stream = [
                json.loads(s)
                for s in (Path(tmp) / "run/v1/events.jsonl").read_text().splitlines()
            ]
            for row in stream:
                COLLECTOR.model.validate(row)
            self.assertEqual(
                [r["mono_ns"] for r in stream if r["kind"] == "boundary"],
                ["100", "110", "120", "130"],
            )
            self.assertTrue((Path(tmp) / "run/SHA256SUMS.json").exists())

    def test_queue_and_disk_exhaustion_record_loss_never_complete(self):
        for disk in (False, True):
            with tempfile.TemporaryDirectory(prefix="perf391-stage4-loss-") as tmp:
                sink = Evidence(
                    Path(tmp) / "run",
                    COLLECTOR,
                    run="synthetic-test",
                    max_events=1,
                    max_disk=16384,
                )
                rows = backend(["worker.start", "worker.end"])
                self.assertTrue(sink.accept(rows[0]))
                self.assertFalse(sink.accept(rows[1]))
                if disk:
                    with patch.object(
                        sink, "_write", side_effect=OSError(errno.ENOSPC, "full")
                    ):
                        sink.drain()
                result = sink.close()
                self.assertFalse(result["complete"])
                self.assertGreater(result["dropped"], 0)
                self.assertTrue(sink.closed)

    def test_browser_origin_clock_documents_and_tid_are_not_node_values(self):
        adapter = BrowserProjection("C", "synthetic-test", "p")
        raw = {
            "run": "synthetic-test",
            "stream": "synthetic-test/p/doc",
            "clock": "browser/p/doc",
            "seq": 1,
            "monotonic_ms": 1.25,
            "phase": "app.request",
            "op": "synthetic-test/p/doc/r1",
            "outcome": "ok",
            "detail": {},
        }
        event = adapter.event(raw)
        contract.validate_event(event)
        self.assertEqual(event["mono_ns"], "1250000")
        self.assertIsNone(event["tid"])
        self.assertIsNone(event["thread_cpu_ns"])
        other = adapter.event(
            {**raw, "stream": "synthetic-test/p/doc2", "clock": "browser/p/doc2"}
        )
        self.assertNotEqual(other["process_uuid"], event["process_uuid"])
        contract.validate_stream([event, other])

    def test_missing_artifact_and_unsupported_browser_phase_do_not_invent_chart(self):
        adapter = BrowserProjection("C", "synthetic-test", "p")
        raw = {
            "run": "synthetic-test",
            "stream": "synthetic-test/p/doc",
            "clock": "browser/p/doc",
            "seq": 1,
            "monotonic_ms": 1,
            "phase": "plot.commit",
            "op": None,
            "outcome": "ok",
            "detail": {},
        }
        event = adapter.event(raw)
        self.assertEqual(event["outcome"], "unavailable")
        with self.assertRaises(ValueError):
            adapter.event({**raw, "phase": "invented"})


class OwnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_shutdown_terminates_and_reaps_only_owned_workers(self):
        with tempfile.TemporaryDirectory(prefix="perf391-stage4-owner-") as tmp:
            owner = Owner(
                Path(tmp) / "run",
                run="synthetic-test",
                sources={"starting_commit": "8faeac62601720cec711d0a6ddc97f18a497cb09"},
            )
            child = owner.spawn([sys.executable, "-c", "import signal; signal.pause()"])
            await owner.close()
            self.assertIsNotNone(child.returncode)
            self.assertFalse(Path(f"/proc/{child.pid}").exists())
            self.assertEqual(owner.manifest["status"], "clean")
            self.assertEqual(owner.manifest["processes"][0]["pid"], child.pid)
            self.assertTrue(owner.manifest["cleanup_commands"])
            await owner.close()

    async def test_repeated_cancel_drains_binding_before_closing_evidence(self):
        with tempfile.TemporaryDirectory(prefix="perf391-stage4-shutdown-") as tmp:
            owner = Owner(Path(tmp) / "run", run="synthetic-test", sources={})
            ready = asyncio.Event()
            release = asyncio.Event()
            order = []

            async def binding():
                ready.set()
                await release.wait()
                order.append("binding")

            owner.register_close("browser", binding)
            owner.register_close("sink", lambda: order.append("sink"))
            closing = asyncio.create_task(owner.close())
            await ready.wait()
            closing.cancel()
            closing.cancel()
            release.set()
            try:
                await closing
            except asyncio.CancelledError:
                pass
            self.assertEqual(order, ["binding", "sink"])
            self.assertEqual(owner.manifest["status"], "clean")

    async def test_failed_cleanup_is_reported_and_remaining_owners_still_close(self):
        with tempfile.TemporaryDirectory(prefix="perf391-stage4-failure-") as tmp:
            owner = Owner(Path(tmp) / "run", run="synthetic-test", sources={})
            done = []

            def bad():
                raise RuntimeError("worker failure")

            owner.register_close("bad", bad)
            owner.register_close("sink", lambda: done.append(True))
            await owner.close()
            self.assertEqual(done, [True])
            self.assertEqual(owner.manifest["status"], "cleanup_failed")


class ResourceScheduleTests(unittest.IsolatedAsyncioTestCase):
    async def test_absolute_host_schedule_skips_late_samples_and_keeps_anchors(self):
        from host import observe_resources

        with tempfile.TemporaryDirectory(prefix="perf391-stage4-hostloop-") as tmp:
            current = [0]
            deadlines = []
            rows = []

            async def wait(deadline):
                deadlines.append(deadline)
                current[0] = deadline + 2500000000

            async def emit(row):
                rows.append(row)

            await observe_resources(
                COLLECTOR,
                emit,
                clock_id="host",
                samples=2,
                now=lambda: current[0],
                wait=wait,
                utc=lambda: 100000000000 + current[0],
                proc_root=Path(tmp),
            )
            self.assertEqual(deadlines, [0, 3000000000])
            self.assertEqual(
                rows[-1],
                {"kind": "summary", "completed": 2, "skipped": 4, "complete": True},
            )
            self.assertEqual(len([r for r in rows if r["kind"] == "anchor"]), 4)


class ScopedOwnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_unrelated_owner_worker_survives_scoped_shutdown(self):
        with tempfile.TemporaryDirectory(prefix="perf391-stage4-isolation-") as tmp:
            a = Owner(Path(tmp) / "a", run="synthetic-a", sources={})
            b = Owner(Path(tmp) / "b", run="synthetic-b", sources={})
            first = a.spawn([sys.executable, "-c", "import signal; signal.pause()"])
            second = b.spawn([sys.executable, "-c", "import signal; signal.pause()"])
            try:
                await a.close()
                self.assertIsNotNone(first.returncode)
                self.assertIsNone(second.poll())
            finally:
                await b.close()
            self.assertIsNotNone(second.returncode)

    async def test_manifest_disk_failure_after_spawn_reaps_the_handle(self):
        with tempfile.TemporaryDirectory(prefix="perf391-stage4-owner-disk-") as tmp:
            owner = Owner(Path(tmp) / "run", run="synthetic-test", sources={})
            original = owner.persist
            calls = [0]

            def persist():
                calls[0] += 1
                if calls[0] > 1:
                    raise OSError(errno.ENOSPC, "full")
                original()

            with patch.object(owner, "persist", side_effect=persist), self.assertRaises(
                OSError
            ):
                owner.spawn([sys.executable, "-c", "import signal; signal.pause()"])
            child = owner.children[0][0]
            self.assertIsNotNone(child.returncode)
            await owner.close()
