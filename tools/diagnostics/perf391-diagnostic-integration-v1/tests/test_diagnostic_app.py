import asyncio
import unittest
from contextlib import contextmanager

import backend_probe as probe
import contract
from diagnostic_app import Boundary


class BoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_request_identity_asgi_send_and_source_worker_join(self):
        calls = []

        async def app(scope, receive, send):
            calls.append("app")
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"{}"})

        async def receive():
            return {"type": "http.disconnect"}

        async def send(message):
            calls.append(message["type"])

        async def pool(fn):
            return fn()

        @contextmanager
        def gate():
            calls.append("lock")
            yield
            calls.append("unlock")

        for path in ("/api/overview-history", "/api/_diagnostic/state"):
            calls.clear()
            probe.configure("C", "synthetic-test")
            boundary = Boundary(
                app,
                run="synthetic-test",
                capture=lambda: {"source": {}},
                gate=gate,
                pool=pool,
            )
            await boundary(
                {
                    "type": "http",
                    "path": path,
                    "method": "GET",
                    "headers": [(b"x-diagnostic-id", b"synthetic-test/p/doc/r1")],
                },
                receive,
                send,
            )
            rows = probe.drain()
            contract.validate_stream(rows)
            self.assertEqual(rows[0]["op_id"], "synthetic-test/p/doc/r1")
            self.assertEqual(rows[0]["phase"], "asgi.entry")
            self.assertEqual(rows[-1]["phase"], "asgi.end")
            if path.endswith("/state"):
                self.assertEqual(calls[:2], ["lock", "unlock"])
                self.assertEqual(
                    len([r for r in rows if r["phase"] == "worker.start"]), 1
                )
            else:
                self.assertEqual(calls[0], "app")
            self.assertTrue(await boundary.drain(timeout=1))

    async def test_malformed_header_local_identity_and_cancellation_keep_real_outcome(
        self,
    ):
        async def bad(*args):
            raise asyncio.CancelledError

        probe.configure("A", "synthetic-test")
        boundary = Boundary(bad, run="synthetic-test")
        with self.assertRaises(asyncio.CancelledError):
            await boundary(
                {
                    "type": "http",
                    "path": "/api/overview-history",
                    "headers": [(b"x-diagnostic-id", b"foreign")],
                },
                None,
                None,
            )
        rows = probe.drain()
        self.assertNotEqual(rows[0]["op_id"], "foreign")
        self.assertEqual(rows[-1]["outcome"], "cancelled")

    async def test_send_failure_not_claimed_as_completed_delivery(self):
        async def app(scope, receive, send):
            await send({"type": "http.response.body", "body": b"x"})

        async def fail(message):
            raise OSError("send")

        probe.configure("C", "synthetic-test")
        boundary = Boundary(app, run="synthetic-test")
        with self.assertRaises(OSError):
            await boundary({"type": "http", "path": "/", "headers": []}, None, fail)
        rows = probe.drain()
        self.assertEqual(
            [r["outcome"] for r in rows if r["phase"] == "asgi.send.end"], ["error"]
        )

    async def test_cancelled_state_waiter_keeps_worker_owned_until_it_finishes(self):
        started = asyncio.Event()
        release = asyncio.Event()

        async def pool(fn):
            started.set()
            await release.wait()
            return fn()

        probe.configure("C", "synthetic-test")
        boundary = Boundary(
            lambda *args: None, run="synthetic-test", capture=dict, pool=pool
        )

        async def send(message):
            pass

        task = asyncio.create_task(
            boundary(
                {
                    "type": "http",
                    "path": "/api/_diagnostic/state",
                    "method": "GET",
                    "headers": [],
                },
                None,
                send,
            )
        )
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertFalse(await boundary.drain(timeout=0))
        release.set()
        self.assertTrue(await boundary.drain(timeout=1))
