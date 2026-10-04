"""Application-owned catalog coordinator, shared persistence and viewer leases."""

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.services.orbital_catalog_client import ProviderFailure, fetch_catalog
from app.services.orbital_catalog_models import (
    eligible_objects,
    utc_epoch,
    validate_catalog,
)
from app.services.orbital_catalog_store import COOLDOWN, OrbitalCatalogStore
from app.services.orbital_viewers import OrbitalViewers


class OrbitalCatalogService:
    def __init__(
        self, directory: Path, client: httpx.AsyncClient | None = None, clock=None
    ):
        self.store = OrbitalCatalogStore(directory)
        self.client = client
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.viewers = OrbitalViewers()
        self._refresh_lock = asyncio.Lock()
        self._runner: asyncio.Task | None = None
        self.closed = False

    @property
    def running(self):
        return self._runner is not None and not self._runner.done()

    async def acquire(self, viewer_id: str):
        if self.closed:
            raise RuntimeError("Orbital service closed")
        expiry = self.viewers.acquire(viewer_id, self.clock())
        if not self.running:
            self._runner = asyncio.create_task(self._coordinate())
        return {"expires_at": expiry.isoformat()}

    async def _stop_without_demand(self):
        if (
            self.viewers.count(self.clock()) == 0
            and self._runner is not asyncio.current_task()
        ):
            await self._stop_runner()

    async def _stop_runner(self):
        runner, self._runner = self._runner, None
        if runner is not None:
            runner.cancel()
            try:
                await runner
            except asyncio.CancelledError:
                pass

    async def release(self, viewer_id: str):
        self.viewers.release(viewer_id)
        await self._stop_without_demand()

    async def _refresh(self):
        async with self._refresh_lock:
            if self.closed or not self.viewers.count(self.clock()):
                return
            try:
                if not await asyncio.to_thread(
                    self.store.reserve_attempt, self.clock()
                ):
                    return
                if self.client is None:
                    self.client = httpx.AsyncClient(timeout=20, follow_redirects=False)
                payload = await fetch_catalog(self.client, self.clock())
                validated = await asyncio.to_thread(validate_catalog, payload)
                validated["acquired_at"] = self.clock().isoformat()
                await asyncio.to_thread(self.store.save_catalog, validated)
            except asyncio.CancelledError:
                # Reservation was persisted before any cancellable network I/O.
                raise
            except (
                httpx.HTTPError,
                TimeoutError,
                ValueError,
                OSError,
                ProviderFailure,
            ) as error:
                suspended = isinstance(error, ProviderFailure) and error.suspended
                retry = (
                    error.retry_after if isinstance(error, ProviderFailure) else None
                )
                try:
                    await asyncio.to_thread(
                        self.store.record_failure, str(error), suspended, retry
                    )
                except OSError:
                    # Never issue another request if persistence fails; disk state
                    # either preserves the reservation or fails closed on read.
                    pass

    async def _coordinate(self):
        while not self.closed and self.viewers.count(self.clock()):
            await self._refresh()
            now = self.clock()
            expiry = self.viewers.next_expiry(now)
            if expiry is None:
                return
            state = await asyncio.to_thread(self.store.read_state)
            due = (
                utc_epoch(state["last_attempt_at"]) + COOLDOWN
                if state["last_attempt_at"]
                else now + COOLDOWN
            )
            if state["retry_after_at"]:
                due = max(due, utc_epoch(state["retry_after_at"]))
            wake = expiry if state["suspended"] else min(expiry, due)
            await asyncio.sleep(max(0.1, (wake - now).total_seconds()))

    async def _envelope(self):
        catalog, state = await asyncio.gather(
            asyncio.to_thread(self.store.read_catalog),
            asyncio.to_thread(self.store.read_state),
        )
        # Revalidate disk contents instead of trusting an external cache edit.
        objects = catalog["objects"]
        if objects:
            try:
                accepted = await asyncio.to_thread(validate_catalog, objects)
                if accepted["generation"] != catalog["generation"]:
                    raise ValueError("Catalog generation mismatch")
                objects = accepted["objects"]
            except (ValueError, KeyError):
                objects = []
        eligible = eligible_objects(objects, self.clock())
        reason = (
            "provider-suspended"
            if state["suspended"]
            else ("ready" if eligible else "expired" if objects else "loading")
        )
        return {
            **catalog,
            **state,
            "objects": eligible,
            "eligible_count": len(eligible),
            "accepted_count": len(objects),
            "active_viewers": self.viewers.count(self.clock()),
            "status": reason,
            "fallback_reason": None if eligible else reason,
        }

    async def get_catalog(self, viewer_id: str):
        if not self.viewers.valid(viewer_id, self.clock()):
            await self._stop_without_demand()
            raise LookupError("A valid orbital viewer lease is required")
        await self._refresh()
        if not self.viewers.valid(viewer_id, self.clock()):
            raise LookupError("Orbital viewer lease expired")
        return await self._envelope()

    async def get_status(self):
        await self._stop_without_demand()
        result = await self._envelope()
        result.pop("objects")
        return result

    async def resume_provider(self):
        await asyncio.to_thread(self.store.resume, self.clock())
        return await self.get_status()

    async def aclose(self):
        self.closed = True
        await self._stop_runner()
        if self.client is not None:
            await self.client.aclose()
