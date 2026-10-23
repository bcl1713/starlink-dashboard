"""Offline behavior tests: no sockets, Docker, or browser execution."""

import asyncio
import hashlib
import json
import io
from contextlib import redirect_stdout
from types import SimpleNamespace
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import frontend_readiness as gate


class ReadinessTests(unittest.TestCase):
    def run_gate(self, replies, state=None, remaining=78):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            now = [0.0]
            calls = []
            replies = iter(replies)

            async def command(argv, cap):
                calls.append(argv)
                if "ps" in argv:
                    return "frontend-id"
                if "inspect" in argv:
                    return json.dumps(state or {"Running": True, "Status": "running"})
                now[0] += 0.05
                reply = next(replies, ConnectionRefusedError("refused"))
                if isinstance(reply, Exception):
                    raise reply
                return reply

            async def sleep(seconds):
                now[0] += seconds

            with patch.object(
                gate.time, "monotonic", side_effect=lambda: now[0]
            ), patch.object(gate.asyncio, "sleep", sleep):
                try:
                    asyncio.run(
                        gate.wait_ready(
                            command,
                            ["docker", "compose"],
                            root,
                            38080,
                            hashlib.sha256(b"index").hexdigest(),
                            remaining,
                            asyncio.Event(),
                        )
                    )
                    error = None
                except Exception as exc:
                    error = exc
            return (
                error,
                json.loads((root / "frontend-readiness.json").read_text()),
                calls,
                now[0],
            )

    def test_immediate_success_requires_expected_status_and_body(self):
        good = json.dumps(
            {"status": 200, "sha256": hashlib.sha256(b"index").hexdigest()}
        )
        error, record, _, _ = self.run_gate([good])
        self.assertIsNone(error)
        self.assertEqual(record["status"], "ready")
        for reply in ['{"status":503}', '{"status":200,"sha256":"wrong"}']:
            error, record, _, _ = self.run_gate([reply])
            self.assertIsNotNone(error)
            self.assertNotEqual(record["status"], "ready")

    def test_delayed_success_retains_failures(self):
        good = json.dumps(
            {"status": 200, "sha256": hashlib.sha256(b"index").hexdigest()}
        )
        error, record, _, _ = self.run_gate([ConnectionRefusedError("refused"), good])
        self.assertIsNone(error)
        self.assertEqual(len(record["attempts"]), 2)
        self.assertIn("refused", record["attempts"][0]["error"])
        self.assertIn("utc_ns", record["attempts"][0])

    def test_exit_and_unhealthy_stop_before_http(self):
        for state in [
            {"Running": False, "Status": "exited", "ExitCode": 1},
            {"Running": True, "Health": {"Status": "unhealthy"}},
        ]:
            error, record, calls, _ = self.run_gate([], state)
            self.assertIsNotNone(error)
            self.assertEqual(record["status"], "container-failed")
            self.assertFalse(any("-c" in c for c in calls))

    def test_refusal_and_request_timeout_fail_within_work_deadline(self):
        for failure in [
            ConnectionRefusedError("refused"),
            TimeoutError("request timeout"),
        ]:
            error, record, _, elapsed = self.run_gate([failure] * 100, remaining=1.1)
            self.assertIsNotNone(error)
            self.assertEqual(
                record["status"],
                "timeout" if isinstance(failure, TimeoutError) else "deadline",
            )
            self.assertLessEqual(elapsed, 1.1)
            self.assertTrue(record["attempts"])


class SnapshotTests(unittest.TestCase):
    def test_diagnostic_failures_do_not_skip_remaining_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            async def command(argv, cap):
                if "ps" in argv and "-aq" in argv:
                    return "owned-frontend"
                raise OSError("injected diagnostic failure")

            asyncio.run(
                gate.snapshot(
                    command,
                    ["docker", "compose"],
                    root,
                    38080,
                    gate.time.monotonic() + 2,
                )
            )
            rows = json.loads((root / "frontend-failure-diagnostics.json").read_text())
            self.assertEqual(
                {r["kind"] for r in rows},
                {
                    "compose-ps",
                    "container-id",
                    "inspect",
                    "port",
                    "frontend-logs",
                    "listeners",
                    "forwarding",
                },
            )
            self.assertEqual(sum("error" in r for r in rows), 6)

    def test_cancelled_gate_persists_evidence_without_http(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stop = asyncio.Event()
            stop.set()

            async def command(*args):
                self.fail("cancelled readiness must not execute a request")

            with self.assertRaises(RuntimeError):
                asyncio.run(
                    gate.wait_ready(
                        command, [], root, 38080, "", gate.time.monotonic() + 5, stop
                    )
                )
            self.assertEqual(
                json.loads((root / "frontend-readiness.json").read_text())["status"],
                "cancelled",
            )


class HttpProbeTests(unittest.TestCase):
    def test_probe_reads_static_route_and_closes_with_a_body_limit(self):
        for size in (5, 262145):
            events = []

            class Connection:
                def __init__(self, host, port, timeout):
                    events.append((host, port, timeout))

                def request(self, method, route, headers):
                    events.append((method, route, headers))

                def getresponse(self):
                    return SimpleNamespace(
                        status=200, read=lambda limit: b"x" * min(limit, size)
                    )

                def close(self):
                    events.append("closed")

            output = io.StringIO()
            with patch("http.client.HTTPConnection", Connection), patch(
                "sys.argv", ["probe", "38080"]
            ), redirect_stdout(output):
                if size > 262144:
                    with self.assertRaisesRegex(ValueError, "body budget"):
                        exec(gate.PROBE, {})
                else:
                    exec(gate.PROBE, {})
                    self.assertEqual(
                        json.loads(output.getvalue()),
                        {"status": 200, "sha256": hashlib.sha256(b"xxxxx").hexdigest()},
                    )
            self.assertEqual(events[0], ("127.0.0.1", 38080, 0.5))
            self.assertEqual(events[1][0:2], ("GET", "/"))
            self.assertEqual(events[-1], "closed")


class CommandBoundTests(unittest.TestCase):
    def test_term_resistant_probe_is_killed_and_reaped_within_its_cap(self):
        import ctypes
        import sys
        from owner import Owner

        libc = ctypes.CDLL(None)
        original = ctypes.c_int()
        self.assertEqual(libc.prctl(37, ctypes.byref(original), 0, 0, 0), 0)
        self.assertEqual(libc.prctl(36, 1, 0, 0, 0), 0)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                owner = Owner(
                    root / "owner",
                    run="synthetic-offline-timeout",
                    sources={},
                    adopt_descendants=True,
                )

                async def check():
                    began = gate.time.monotonic()
                    with (root / "child.log").open("wb") as log:
                        child = owner.spawn(
                            gate.bounded_argv(
                                [
                                    sys.executable,
                                    "-c",
                                    "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(30)",
                                ],
                                0.4,
                            ),
                            stdout=log,
                        )
                        try:
                            await asyncio.wait_for(
                                asyncio.to_thread(child.wait), timeout=2
                            )
                        finally:
                            await owner.close()
                    self.assertNotEqual(child.returncode, 0)
                    self.assertLess(gate.time.monotonic() - began, 1)
                    self.assertEqual(owner.manifest["status"], "clean")
                    self.assertFalse(owner.manifest["adopted_survivors"])

                asyncio.run(check())
        finally:
            libc.prctl(36, original.value, 0, 0, 0)
