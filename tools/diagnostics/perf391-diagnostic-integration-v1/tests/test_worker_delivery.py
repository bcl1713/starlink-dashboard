"""Execute the original Starlette/AnyIO pool with real limiter and barriers."""

import asyncio
import importlib
import sys
import threading
import unittest
from pathlib import Path

import anyio
from starlette.concurrency import run_in_threadpool

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))


class WorkerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.assertTrue((PACKAGE / "workers.py").is_file(), "worker adapter missing")
        self.w = importlib.import_module("workers")
        self.p = importlib.import_module("backend_probe")
        self.p.configure("C", "offline")

    async def test_return_kwargs_and_error_identity(self):
        def work(*, value):
            return value

        value = object()
        self.assertIs(
            await self.w.await_pool(
                "worker", "job", run_in_threadpool, work, value=value
            ),
            value,
        )
        events = self.p.drain()
        self.assertEqual(
            [e["phase"] for e in events],
            ["worker.dispatch", "worker.start", "worker.end", "worker.returned"],
        )
        self.assertNotEqual(events[0]["tid"], events[1]["tid"])
        self.assertEqual(len({e["clock_id"] for e in events}), 1)
        self.assertEqual(events[0]["tid"], events[3]["tid"])
        error = ValueError("same object")

        def fail():
            raise error

        with self.assertRaises(ValueError) as raised:
            await self.w.await_pool("worker", "bad", run_in_threadpool, fail)
        self.assertIs(raised.exception, error)
        self.assertEqual(
            [e["outcome"] for e in self.p.drain()], ["ok", "ok", "error", "error"]
        )

    async def test_actual_limiter_queue_and_completion_delivery(self):
        limiter = anyio.to_thread.current_default_thread_limiter()
        old = limiter.total_tokens
        limiter.total_tokens = 1
        started, release, finished = (
            threading.Event(),
            threading.Event(),
            threading.Event(),
        )

        def work():
            started.set()
            try:
                if not release.wait(5):
                    raise TimeoutError("test barrier")
                return 42
            finally:
                finished.set()

        task = None
        try:
            await limiter.acquire()
            task = asyncio.create_task(
                self.w.await_pool("worker", "queued", run_in_threadpool, work)
            )
            await asyncio.sleep(0)
            self.assertFalse(started.is_set())
            self.assertEqual([e["phase"] for e in self.p.drain()], ["worker.dispatch"])
            limiter.release()
            while not started.is_set():
                await asyncio.sleep(0)
            # Block this event loop until the worker finishes. Delivery must be
            # separately recorded after the loop regains control.
            release.set()
            self.assertTrue(finished.wait(5))
            self.assertFalse(task.done())
            events = self.p.drain()
            self.assertEqual(
                [e["phase"] for e in events], ["worker.start", "worker.end"]
            )
            self.assertEqual(await task, 42)
            self.assertEqual([e["phase"] for e in self.p.drain()], ["worker.returned"])
        finally:
            release.set()
            if limiter.borrowed_tokens and task is None:
                limiter.release()
            if task:
                await asyncio.gather(task, return_exceptions=True)
            limiter.total_tokens = old

    async def test_cancellation_matches_pool_before_admission_and_during_work(self):
        for point in ("queued", "running", "completed"):
            snapshots = []
            for instrumented in (False, True):
                self.p.configure("C", "offline")
                started, release, finished = (
                    threading.Event(),
                    threading.Event(),
                    threading.Event(),
                )
                effects = []
                limiter = anyio.to_thread.current_default_thread_limiter()
                old = limiter.total_tokens
                limiter.total_tokens = 1

                def work():
                    started.set()
                    try:
                        if not release.wait(5):
                            raise TimeoutError("test barrier")
                        effects.append("complete")
                        return "result"
                    finally:
                        finished.set()

                task = None
                held = False
                try:
                    if point == "queued":
                        await limiter.acquire()
                        held = True
                    awaitable = (
                        self.w.await_pool("worker", "cancel", run_in_threadpool, work)
                        if instrumented
                        else run_in_threadpool(work)
                    )
                    task = asyncio.create_task(awaitable)
                    await asyncio.sleep(0)
                    if point != "queued":
                        while not started.is_set():
                            await asyncio.sleep(0)
                    if point == "completed":
                        release.set()
                        self.assertTrue(finished.wait(5))
                    task.cancel()
                    result = await asyncio.gather(task, return_exceptions=True)
                    release.set()
                    if started.is_set():
                        self.assertTrue(finished.wait(5))
                    snapshots.append(
                        (type(result[0]).__name__, effects[:], started.is_set())
                    )
                    if instrumented:
                        events = self.p.drain()
                        returned = [
                            e for e in events if e["phase"] == "worker.returned"
                        ]
                        self.assertEqual(len(returned), 1)
                        self.assertEqual(returned[0]["outcome"], "cancelled")
                finally:
                    release.set()
                    if held:
                        limiter.release()
                    if task:
                        await asyncio.gather(task, return_exceptions=True)
                    limiter.total_tokens = old
            self.assertEqual(snapshots[0], snapshots[1], point)

    async def test_all_worker_boundaries_share_child_and_parent_ids(self):
        with self.p.operation("request", "history"):
            self.assertEqual(
                await self.w.await_pool(
                    "worker", "child", run_in_threadpool, lambda: 1
                ),
                1,
            )
        events = self.p.drain()
        self.assertEqual({e["op_id"] for e in events}, {"child"})
        self.assertEqual({e["parent_op_id"] for e in events}, {"request"})
        self.assertEqual({e["operation_type"] for e in events}, {"history"})

    async def test_anyio_cancel_scope_keeps_default_running_worker_shield(self):
        snapshots = []
        for instrumented in (False, True):
            self.p.configure("C", "offline")
            started, release, finished = (
                threading.Event(),
                threading.Event(),
                threading.Event(),
            )
            values = []

            def work():
                started.set()
                try:
                    if not release.wait(5):
                        raise TimeoutError("barrier")
                    return 42
                finally:
                    finished.set()

            async def job():
                value = (
                    await self.w.await_pool(
                        "worker", "shielded", run_in_threadpool, work
                    )
                    if instrumented
                    else await run_in_threadpool(work)
                )
                values.append(value)

            try:
                async with anyio.create_task_group() as group:
                    group.start_soon(job)
                    while not started.is_set():
                        await anyio.sleep(0)
                    group.cancel_scope.cancel()
                    self.assertFalse(finished.is_set())
                    release.set()
            finally:
                release.set()
            self.assertTrue(finished.is_set())
            snapshots.append(values)
            events = self.p.drain()
            if instrumented:
                self.assertEqual(
                    [e["phase"] for e in events],
                    [
                        "worker.dispatch",
                        "worker.start",
                        "worker.end",
                        "worker.returned",
                    ],
                )
                self.assertEqual(events[-1]["outcome"], "ok")
        self.assertEqual(snapshots, [[42], [42]])

    async def test_sink_faults_do_not_change_worker_semantics(self):
        with self.p.faults():
            self.assertEqual(
                await self.w.await_pool("worker", "job", run_in_threadpool, lambda: 7),
                7,
            )
        self.assertGreater(self.p.stats()["failures"], 0)
