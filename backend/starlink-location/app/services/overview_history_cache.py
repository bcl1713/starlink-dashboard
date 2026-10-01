"""Demand-driven, per-process incremental history with one bounded refresh."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from app.services.overview_history_prometheus import OverviewHistoryQueryPlan

OVERLAP_SECONDS = 10
MAX_CATCHUP_SECONDS = 30
RECONCILE_SECONDS = 300
REFRESH_TIMEOUT_SECONDS = 5


class OverviewHistoryReader:
    """Publish replacement snapshots, sharing completed results and active work."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        get_window_seconds: Callable[[], int],
        time_source: Callable[[], float],
        monotonic_source: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._get_window_seconds = get_window_seconds
        self._time_source = time_source
        self._monotonic_source = monotonic_source
        self._window: int | None = None
        self._generation = 0
        self._snapshot: dict | None = None
        self._public: dict | None = None
        self._flight: asyncio.Task[None] | None = None
        self._last_full = 0
        self._last_clock: int | None = None
        self._identity: dict = {}
        self._failure: str | None = None
        self._retry_at = 0.0
        self._failures = 0
        self._closed = False

    def invalidate(self) -> None:
        """Discard this generation, including any unpublished in-flight result."""
        self._generation += 1
        self._snapshot = self._public = None
        self._identity = {}
        self._failure = None
        self._retry_at = 0
        self._failures = 0
        self._last_clock = None

    async def read(self) -> dict:
        """Refresh on demand; callers spanning seconds share the active refresh."""
        from app.services.overview_history_prometheus import (
            OverviewHistoryPrometheusResponseError,
            plan_overview_history_query,
        )

        while not self._closed:
            window = self._get_window_seconds()
            now = int(self._time_source())
            if window != self._window or (
                self._last_clock is not None and now < self._last_clock
            ):
                self.invalidate()
                self._window = window
            self._last_clock = now
            plan = plan_overview_history_query(
                end_timestamp_seconds=now, window_seconds=window
            )
            if self._failure is not None and self._monotonic_source() < self._retry_at:
                raise OverviewHistoryPrometheusResponseError(self._failure)
            if (
                self._public is not None
                and self._public["end_timestamp_seconds"] == plan.end_timestamp_seconds
            ):
                return self._public
            generation = self._generation
            flight = self._flight
            if flight is None:
                flight = asyncio.create_task(self._refresh(plan, window, generation))
                self._flight = flight
                # Consume errors even when every HTTP waiter cancels.
                flight.add_done_callback(
                    lambda task: task.exception() if not task.cancelled() else None
                )
            try:
                await asyncio.shield(flight)
            except Exception:
                if generation != self._generation:
                    continue
                raise
            if generation != self._generation or window != self._get_window_seconds():
                continue
            if self._public is not None:
                return self._public
        raise OverviewHistoryPrometheusResponseError(
            "Overview history reader is closed"
        )

    async def _refresh(
        self, plan: OverviewHistoryQueryPlan, window: int, generation: int
    ) -> None:
        from app.services.overview_history_merge import merge_history
        from app.services.overview_history_prometheus import (
            OverviewHistoryPrometheusResponseError,
            query_overview_history_bundle,
        )

        previous = self._snapshot
        end = plan.end_timestamp_seconds
        full = (
            previous is None
            or end - previous["end_timestamp_seconds"]
            > max(MAX_CATCHUP_SECONDS, plan.step_seconds)
            or end - self._last_full >= RECONCILE_SECONDS
        )
        query_plan = plan
        if not full:
            assert previous is not None
            overlap_start = (
                (previous["end_timestamp_seconds"] - OVERLAP_SECONDS)
                // plan.step_seconds
                * plan.step_seconds
            )
            query_plan = replace(
                plan,
                start_timestamp_seconds=max(
                    plan.start_timestamp_seconds, overlap_start
                ),
            )

        async def fetch(selected_plan: OverviewHistoryQueryPlan) -> dict:
            return await query_overview_history_bundle(
                self._client,
                end_timestamp_seconds=end,
                window_seconds=window,
                plan=selected_plan,
                include_identity=True,
            )

        try:
            async with asyncio.timeout(REFRESH_TIMEOUT_SECONDS):
                incoming = await fetch(query_plan)
                identity = incoming["_identity"]
                changed = any(
                    metric in self._identity and value != self._identity[metric]
                    for metric, value in identity.items()
                )
                recovered = previous is not None and any(
                    old["state"] == "unavailable"
                    and incoming["rolling_5m"][metric]["state"] == "available"
                    for metric, old in previous["rolling_5m"].items()
                )
                if not full and (changed or recovered):
                    incoming = await fetch(plan)
                    full = True
                snapshot = incoming
                if not full:
                    assert previous is not None
                    snapshot = merge_history(
                        previous, incoming, query_plan.start_timestamp_seconds
                    )
            if generation == self._generation and window == self._get_window_seconds():
                self._snapshot = snapshot
                self._public = {
                    key: value
                    for key, value in snapshot.items()
                    if not key.startswith("_")
                }
                self._identity.update(identity)
                if full:
                    self._last_full = end
                self._failure = None
                self._failures = 0
        except (httpx.HTTPError, ValueError, TimeoutError) as error:
            if generation == self._generation:
                self._failures = min(4, self._failures + 1)
                delay = min(5, 2 ** min(self._failures - 1, 3))
                self._retry_at = self._monotonic_source() + delay
                self._failure = "Overview history refresh failed"
                raise OverviewHistoryPrometheusResponseError(self._failure) from error
        finally:
            self._flight = None

    async def aclose(self) -> None:
        """Cancel and drain shared work before the lifecycle closes its client."""
        self._closed = True
        self.invalidate()
        flight = self._flight
        if flight is not None:
            flight.cancel()
            await asyncio.gather(flight, return_exceptions=True)
