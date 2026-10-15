"""Bounded query counters and optional append-only diagnostic evidence."""

from __future__ import annotations

import asyncio
import json
import time
from collections import Counter
from pathlib import Path

import httpx


class QueryTrace(httpx.AsyncBaseTransport):
    """Observe upstream work without retaining query responses or uptime lists."""

    def __init__(self, transport: httpx.AsyncBaseTransport, output: Path | None = None):
        self.transport = transport
        self.output = output
        self.queries = 0
        self.evaluation_points = 0
        self.active = 0
        self.max_active = 0
        self.errors = 0
        self.spans: Counter[int] = Counter()

    def reset_spans(self) -> None:
        self.spans.clear()

    async def write_record(self, row: dict, output: Path | None = None) -> None:
        destination = output or self.output
        if destination is not None:
            await asyncio.to_thread(
                _append, destination, json.dumps(row, separators=(",", ":")) + "\n"
            )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        began = time.perf_counter()
        self.active += 1
        self.max_active = max(self.active, self.max_active)
        self.queries += 1
        params = request.url.params
        start, end, step = (
            int(float(params.get(key, "0"))) for key in ("start", "end", "step")
        )
        span = end - start
        series = 11 if params.get("query", "").startswith("{") else 1
        points = ((span // step) + 1) * series if step > 0 else 0
        self.evaluation_points += points
        self.spans[span] += 1
        status = 0
        try:
            response = await self.transport.handle_async_request(request)
            await response.aread()
            status = response.status_code
            if status >= 400:
                self.errors += 1
            return response
        except (httpx.HTTPError, TimeoutError):
            self.errors += 1
            raise
        finally:
            self.active -= 1
            if self.output is not None:
                row = {
                    "kind": "upstream",
                    "monotonic_seconds": time.monotonic(),
                    "elapsed_ms": (time.perf_counter() - began) * 1000,
                    "start": start,
                    "end": end,
                    "step": step,
                    "evaluation_points": points,
                    "status": status,
                    "active": self.active,
                }
                await self.write_record(row)

    async def aclose(self) -> None:
        await self.transport.aclose()


def _append(output: Path, encoded: str) -> None:
    with output.open("a") as stream:
        stream.write(encoded)
