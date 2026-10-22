"""Diagnostic-only ASGI wrapper; construction never imports/starts an application.

The owner supplies the exact frozen synthetic capture function and existing
repository gate. Worker tracking wraps only that dedicated state worker and
retains the original Starlette/AnyIO pool. No globals are monkey patched.
"""

import asyncio
import re
import threading
import time
from contextlib import nullcontext

from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

import backend_probe as probe
from workers import await_pool


class Boundary:
    def __init__(self, app, *, run, capture=None, gate=None, pool=run_in_threadpool):
        if not re.fullmatch(r"synthetic-[A-Za-z0-9_-]{1,22}", run):
            raise ValueError("synthetic run")
        self.app, self.run, self.capture, self.gate, self.pool = (
            app,
            run,
            capture,
            gate,
            pool,
        )
        self.active = set()
        self.pending = set()
        self.lock = threading.Lock()
        self.closed = False

    def _capture(self):
        token = object()
        with self.lock:
            self.active.add(token)
        try:
            with self.gate() if self.gate else nullcontext():
                return self.capture()
        finally:
            with self.lock:
                self.active.discard(token)

    async def drain(self, *, timeout=2):
        self.closed = True
        deadline = time.monotonic() + timeout
        while True:
            with self.lock:
                active = bool(self.active)
            if not active and not self.pending:
                return True
            if time.monotonic() >= deadline:
                return False
            await asyncio.sleep(0.01)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        values = [
            v for k, v in scope.get("headers", []) if k.lower() == b"x-diagnostic-id"
        ]
        request = None
        if len(values) == 1:
            try:
                text = values[0].decode("ascii")
                if text.startswith(self.run + "/") and re.fullmatch(
                    r"[\x21-\x7e]{1,96}", text
                ):
                    request = text
            except UnicodeError:
                pass
        request = request or probe.new_operation("backend-local")
        kind = (
            "source_observer"
            if scope.get("path") == "/api/_diagnostic/state"
            else (
                "history"
                if scope.get("path") == "/api/overview-history"
                else "lifecycle"
            )
        )
        with probe.operation(request, kind):
            probe.mark("asgi.entry", identity={"request_id": request})

            async def observed_receive():
                message = await receive()
                if message["type"] == "http.disconnect":
                    probe.mark("asgi.disconnect", outcome="cancelled")
                return message

            async def observed_send(message):
                if message["type"] == "http.response.start":
                    probe.mark("asgi.headers")
                probe.mark("asgi.send.begin")
                try:
                    await send(message)
                except BaseException as error:
                    probe.mark("asgi.send.end", outcome=probe.outcome(error))
                    raise
                probe.mark("asgi.send.end")

            try:
                if kind == "source_observer":
                    if self.capture is None or self.closed:
                        response = JSONResponse(
                            {"unavailable": "state capture unavailable"},
                            status_code=503,
                        )
                    elif scope.get("method") != "GET":
                        response = JSONResponse(
                            {"error": "GET required"}, status_code=405
                        )
                    else:
                        task = asyncio.create_task(
                            await_pool(
                                "source_observer",
                                probe.new_operation("state-worker"),
                                self.pool,
                                self._capture,
                            )
                        )
                        self.pending.add(task)

                        def completed(work):
                            self.pending.discard(work)
                            if not work.cancelled():
                                work.exception()

                        task.add_done_callback(completed)
                        value = await asyncio.shield(task)
                        response = JSONResponse(value)
                    await response(scope, observed_receive, observed_send)
                else:
                    await self.app(scope, observed_receive, observed_send)
            except BaseException as error:
                probe.mark("asgi.end", outcome=probe.outcome(error))
                raise
            probe.mark("asgi.end")
