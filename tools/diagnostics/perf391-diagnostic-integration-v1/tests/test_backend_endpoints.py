"""Direct async route calls only: no HTTP requests, service or browser."""

import asyncio
import unittest
from types import SimpleNamespace as NS

from backend_support import functions, probe, roots
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

import contract

router = NS(get=lambda *a, **kw: lambda fn: fn)


class EndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_metrics_and_status_keep_pool_callable_kwargs_and_errors(self):
        for role in ("A", "C"):
            for endpoint in ("metrics", "status"):
                for error in (False, True):
                    results = []
                    for patched in (False, True):
                        root = roots(role)[patched]
                        calls = []
                        failure = ValueError("same failure")

                        def payload(*args):
                            calls.append(("payload", args))
                            if error:
                                raise failure
                            return (
                                "# EOF\n"
                                if endpoint == "metrics"
                                else {"status": "ready"}
                            )

                        def record(value):
                            calls.append(("record", value))

                        env = {
                            "router": router,
                            "status": NS(HTTP_200_OK=200),
                            "StatusResponse": object,
                            "run_in_threadpool": run_in_threadpool,
                            "_prepare_metrics": payload,
                            "_status_payload": payload,
                            "_record_exposition": record,
                        }
                        path = (
                            "app/api/metrics_export.py"
                            if endpoint == "metrics"
                            else "app/api/status.py"
                        )
                        name = "get_metrics" if endpoint == "metrics" else "status"
                        ns = functions(root, path, [name], env)
                        probe.configure(role, "offline")
                        with probe.operation("request", "lifecycle"):
                            try:
                                value = (
                                    await ns[name]("route", "poi")
                                    if endpoint == "metrics"
                                    else await ns[name]()
                                )
                            except ValueError as actual:
                                self.assertIs(actual, failure)
                                value = type(actual).__name__
                        results.append((value, calls))
                        events = probe.drain()
                        if patched:
                            self.assertEqual(
                                [e["phase"] for e in events],
                                [
                                    "worker.dispatch",
                                    "worker.start",
                                    "worker.end",
                                    "worker.returned",
                                ],
                            )
                            self.assertEqual(
                                {e["parent_op_id"] for e in events}, {"request"}
                            )
                            self.assertEqual(
                                {e["operation_type"] for e in events},
                                {"scrape" if endpoint == "metrics" else "lifecycle"},
                            )
                            contract.validate_stream(events)
                    self.assertEqual(results[0], results[1], (role, endpoint, error))

    async def test_history_response_503_error_and_cancel_have_no_worker_span(self):
        class ReaderError(Exception):
            pass

        for role in ("A", "C"):
            for case in ("normal", "uninitialized", "reader_error", "cancel"):
                outputs = []
                for patched in (False, True):

                    async def reader():
                        if case == "reader_error":
                            raise ReaderError("read")
                        if case == "cancel":
                            raise asyncio.CancelledError("cancel")
                        return {"series": [1, None, 3], "window": 1800}

                    root = roots(role)[patched]
                    env = {
                        "router": router,
                        "_overview_history_reader": (
                            None if case == "uninitialized" else reader
                        ),
                        "HTTPException": HTTPException,
                        "JSONResponse": JSONResponse,
                        "httpx": NS(HTTPError=ReaderError),
                        "OverviewHistoryPrometheusResponseError": ReaderError,
                    }
                    ns = functions(
                        root,
                        "app/api/overview_history.py",
                        ["get_overview_history"],
                        env,
                    )
                    probe.configure(role, "offline")
                    try:
                        response = await ns["get_overview_history"]()
                        output = (
                            response.status_code,
                            response.body,
                            tuple(response.raw_headers),
                        )
                    except HTTPException as error:
                        output = (type(error).__name__, error.status_code, error.detail)
                    except asyncio.CancelledError as error:
                        output = (type(error).__name__, str(error))
                    outputs.append(output)
                    events = probe.drain()
                    if patched:
                        self.assertEqual(
                            [e["phase"] for e in events],
                            ["history.begin", "history.end"],
                        )
                        self.assertEqual(
                            events[-1]["outcome"],
                            (
                                "ok"
                                if case == "normal"
                                else "cancelled" if case == "cancel" else "error"
                            ),
                        )
                        contract.validate_stream(events)
                self.assertEqual(outputs[0], outputs[1], (role, case))

    async def test_refresh_owner_keeps_delivery_and_repeated_cancel_drain(self):
        import threading

        from backend_support import module_at, modules

        outputs = []
        for patched in (False, True):
            root = roots("C")[patched]
            frames = module_at(root, "app/core/metrics/frames.py")
            store = frames.FrameStore(())
            with modules(
                **{"app.core.metrics.prometheus_metrics": {"FRAME_STORE": store}}
            ):
                lifecycle = module_at(root, "app/core/metrics/lifecycle.py")
            started, release, finished = (
                threading.Event(),
                threading.Event(),
                threading.Event(),
            )
            effects = []

            def refresh():
                started.set()
                try:
                    if not release.wait(5):
                        raise TimeoutError("barrier")
                    effects.append("refresh")
                    return True
                finally:
                    finished.set()

            owner = lifecycle.MetricsRefreshOwner(
                refresh, background_enabled=True, store=store
            )
            probe.configure("C", "offline")
            task = asyncio.create_task(owner.refresh_without_collection(force=True))
            try:
                while not started.is_set():
                    await asyncio.sleep(0)
                task.cancel()
                await asyncio.sleep(0)
                task.cancel()
                await asyncio.sleep(0)
                self.assertFalse(task.done())
                release.set()
                outcome = (await asyncio.gather(task, return_exceptions=True))[0]
                outputs.append((type(outcome).__name__, effects, owner._work))
                self.assertTrue(finished.is_set())
            finally:
                release.set()
                await asyncio.gather(task, return_exceptions=True)
                await owner.close()
            events = probe.drain()
            if patched:
                self.assertEqual(
                    [e["phase"] for e in events],
                    [
                        "refresh.dispatch",
                        "refresh.start",
                        "refresh.end",
                        "refresh.returned",
                    ],
                )
                self.assertEqual(
                    {e["operation_type"] for e in events}, {"derived_refresh"}
                )
                contract.validate_stream(events)
        self.assertEqual(outputs[0], outputs[1])
