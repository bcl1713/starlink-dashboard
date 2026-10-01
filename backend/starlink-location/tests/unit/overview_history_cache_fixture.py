"""Shared deterministic Prometheus fixture for cache controls."""

import asyncio

import httpx
import pytest

from app.services.overview_history_cache import OverviewHistoryReader
from app.services.overview_history_prometheus import OVERVIEW_HISTORY_METRICS
from app.services.overview_history_rollups import ROLLUP_METRICS


class PrometheusFixture:
    """Deterministic authoritative traces, corrections and transport failures."""

    def __init__(self):
        self.now = 10_000
        self.window = 1800
        self.requests = []
        self.deleted = set()
        self.invalid = set()
        self.corrections = {}
        self.label = "first"
        self.ambiguous = False
        self.fail_raw = False
        self.fail_rollup = False
        self.started = asyncio.Event()
        self.release = None
        self.rollup_release = None
        self.active = 0
        self.max_active = 0

    async def handle(self, request):
        self.requests.append(dict(request.url.params))
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        self.started.set()
        try:
            if self.release is not None:
                await self.release.wait()
            params = request.url.params
            raw = params["query"].startswith("{")
            if not raw and self.rollup_release is not None:
                await self.rollup_release.wait()
            if (raw and self.fail_raw) or (not raw and self.fail_rollup):
                return httpx.Response(503)
            times = range(
                int(params["start"]), int(params["end"]) + 1, int(params["step"])
            )
            metrics = (
                OVERVIEW_HISTORY_METRICS
                if raw
                else [metric for metric in ROLLUP_METRICS if metric in params["query"]]
            )
            result = []
            for metric in metrics:
                values = [
                    [
                        t,
                        (
                            "NaN"
                            if raw and t in self.invalid
                            else str(self.corrections.get(t, t % 73))
                        ),
                    ]
                    for t in times
                    if t not in self.deleted and t % 17 != 0
                ]
                labels = {
                    "instance": self.label,
                    **({"__name__": metric} if raw else {}),
                }
                entry = {"metric": labels, "values": values}
                result.append(entry)
                if raw and self.ambiguous and metric == ROLLUP_METRICS[0]:
                    result.append({**entry, "metric": {**labels, "instance": "second"}})
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": {"resultType": "matrix", "result": result},
                },
            )
        finally:
            self.active -= 1

    def reader(self, client):
        return OverviewHistoryReader(
            client,
            get_window_seconds=lambda: self.window,
            time_source=lambda: self.now,
            monotonic_source=lambda: self.now,
        )


@pytest.fixture
async def source():
    fixture = PrometheusFixture()
    async with httpx.AsyncClient(
        base_url="http://prometheus", transport=httpx.MockTransport(fixture.handle)
    ) as client:
        yield fixture, client, fixture.reader(client)
