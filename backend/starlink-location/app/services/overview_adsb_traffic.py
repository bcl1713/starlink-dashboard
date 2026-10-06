"""One application-owned acquisition scheduler, ephemeral cache and source backoff."""

import asyncio
from collections.abc import Callable

from app.models.overview_adsb import (
    AdsbContact,
    AdsbSettings,
    AdsbSourceStatus,
    AdsbTrafficBundle,
)
from app.services.adsb_lol import AdsbLolProvider, AdsbProviderError
from app.services.overview_adsb_selection import position_state, select_contacts
from app.services.overview_adsb_settings import AdsbSettingsStore


class AdsbTrafficService:
    def __init__(
        self,
        store: AdsbSettingsStore,
        provider: AdsbLolProvider,
        time_source: Callable[[], float],
        monotonic_source: Callable[[], float],
    ) -> None:
        self._store, self._provider = store, provider
        self._time, self._monotonic = time_source, monotonic_source
        self._settings: AdsbSettings | None = None
        self._generation = 0
        self._contacts: dict[str, AdsbContact] = {}
        self._sources: dict[str, AdsbSourceStatus] = {}
        self._failures: dict[str, int] = {}
        self._retry: dict[str, float] = {}
        self._next_cycle = 0.0
        self._catalog_until = 0.0
        self._attempts = 0
        self._lock = asyncio.Lock()
        self._wake = asyncio.Event()
        self._scheduler: asyncio.Task | None = None
        self._cycle: asyncio.Task | None = None
        self._closed = False

    def _clear(self) -> None:
        self._contacts.clear()
        self._sources.clear()
        self._failures.clear()
        self._retry.clear()

    def _cancel_cycle(self) -> None:
        if self._cycle is not None and not self._cycle.done():
            self._cycle.cancel()

    @staticmethod
    def _source_keys(settings: AdsbSettings) -> set[str]:
        if not settings.enabled:
            return set()
        keys = {
            f"hex:{h}"
            for h in settings.include_hexes
            if h not in settings.exclude_hexes
        }
        if settings.mode == "military_and_included":
            keys.add("military")
        return keys

    def _sync_settings(self) -> AdsbSettings:
        try:
            settings = self._store.get()
        except (OSError, ValueError, TypeError):
            self._generation += 1
            self._settings = None
            self._cancel_cycle()
            self._contacts.clear()
            raise
        if self._settings is None or settings.revision != self._settings.revision:
            self._generation += 1
            self._cancel_cycle()
            self._settings = settings
            if not settings.enabled:
                self._contacts.clear()
            else:
                self._prune(settings)
            keys = self._source_keys(self._acquisition_settings(settings))
            if any(key.startswith("hex:") for key in keys):
                keys.add("included")
            now = self._monotonic()
            for mapping in (self._sources, self._failures, self._retry):
                for key in list(mapping):
                    # Configuration must not reset an upstream rate limit.
                    # Keep inactive failure state only until its deadline.
                    if key not in keys and self._retry.get(key, 0) <= now:
                        del mapping[key]
        return settings

    @staticmethod
    def _catalog_settings(settings: AdsbSettings) -> AdsbSettings:
        return settings.model_copy(
            update={
                "mode": "military_and_included",
                "exclude_hexes": [],
                "callsign_substrings": [],
            }
        )

    def _acquisition_settings(self, settings: AdsbSettings) -> AdsbSettings:
        if self._monotonic() < self._catalog_until:
            return self._catalog_settings(settings)
        return settings

    def _prune(self, settings: AdsbSettings) -> None:
        self._contacts = {
            c.hex: c
            for c in select_contacts(
                self._contacts.values(),
                self._catalog_settings(settings),
                self._time() * 1000,
            )
        }

    def settings_changed(self) -> None:
        self._sync_settings()
        self._wake.set()

    def read(self) -> AdsbTrafficBundle:
        settings = self._sync_settings()
        self._prune(settings)
        keys = self._source_keys(settings)
        return AdsbTrafficBundle(
            settings_revision=settings.revision,
            generated_at_ms=self._time() * 1000,
            contacts=select_contacts(
                self._contacts.values(), settings, self._time() * 1000
            ),
            sources=[self._sources[k] for k in sorted(self._sources) if k in keys],
        )

    def read_catalog(self) -> AdsbTrafficBundle:
        settings = self._sync_settings()
        if settings.enabled:
            # Reads only renew demand; acquisition remains owned by the shared
            # scheduler, including its cadence and upstream retry deadlines.
            self._catalog_until = self._monotonic() + 30
            self._wake.set()
        self._prune(settings)
        catalog_settings = self._catalog_settings(settings)
        keys = self._source_keys(catalog_settings)
        return AdsbTrafficBundle(
            settings_revision=settings.revision,
            generated_at_ms=self._time() * 1000,
            contacts=select_contacts(
                self._contacts.values(), catalog_settings, self._time() * 1000
            ),
            sources=[self._sources[k] for k in sorted(self._sources) if k in keys],
        )

    async def start(self) -> None:
        if self._scheduler is None:
            self._closed = False
            self._scheduler = asyncio.create_task(
                self._run(), name="overview-adsb-scheduler"
            )

    async def aclose(self) -> None:
        self._closed = True
        tasks = [t for t in (self._scheduler, self._cycle) if t is not None]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._scheduler = self._cycle = None
        self._clear()

    def _ensure_cycle(self) -> asyncio.Task | None:
        try:
            settings = self._sync_settings()
        except (OSError, ValueError, TypeError):
            return None
        if not settings.enabled or self._closed:
            return None
        if self._cycle is not None and not self._cycle.done():
            return self._cycle
        if self._monotonic() < self._next_cycle:
            return None
        self._cycle = asyncio.create_task(
            self._acquire(self._acquisition_settings(settings), self._generation),
            name="overview-adsb-cycle",
        )
        return self._cycle

    async def refresh_once(self) -> None:
        task = self._ensure_cycle()
        if task is not None:
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                if asyncio.current_task().cancelling():
                    raise

    async def _run(self) -> None:
        while not self._closed:
            self._wake.clear()
            self._ensure_cycle()
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=1)
            except TimeoutError:
                pass

    async def _fetch_sources(self, keys: list[str], generation: int) -> bool:
        # Included lookup failures belong to the shared batch, independent of
        # list membership. Settings edits must not bypass a provider deadline.
        military = keys == ["military"]
        key = "military" if military else "included"
        hex_codes = [source[4:] for source in keys] if not military else []
        if generation != self._generation or self._monotonic() < self._retry.get(
            key, 0
        ):
            return False
        self._attempts += 1
        try:
            result = await (
                self._provider.fetch_military()
                if military
                else self._provider.fetch_hexes(hex_codes)
            )
        except asyncio.CancelledError:
            raise
        except AdsbProviderError as error:
            if generation != self._generation:
                return False
            failures = self._failures.get(key, 0) + 1
            self._failures[key] = failures
            delay = min(15 * 2 ** min(failures - 1, 5), 300)
            if (
                isinstance(error, AdsbProviderError)
                and error.retry_after_seconds is not None
            ):
                delay = max(delay, error.retry_after_seconds)
            self._retry[key] = self._monotonic() + delay
            for source_key in keys:
                # Keep attempted source status through settings round trips,
                # while the shared key remains the acquisition gate.
                self._retry[source_key] = self._retry[key]
                previous = self._sources.get(
                    source_key, AdsbSourceStatus(key=source_key)
                )
                self._sources[source_key] = AdsbSourceStatus(
                    key=source_key,
                    last_success_at_ms=previous.last_success_at_ms,
                    error="Provider acquisition failed",
                    retry_at_ms=(self._time() + delay) * 1000,
                )
            return False
        try:
            self._sync_settings()
        except (OSError, ValueError, TypeError):
            return False
        if generation != self._generation:
            return False
        if military:
            self._failures.pop(key, None)
            self._retry.pop(key, None)
        for source_key in keys:
            self._retry.pop(source_key, None)
            self._sources[source_key] = AdsbSourceStatus(
                key=source_key, last_success_at_ms=result.acquired_at_ms
            )
        requested = set(hex_codes)
        for contact in result.contacts:
            if not military and contact.hex not in requested:
                continue
            previous_contact = self._contacts.get(contact.hex)
            if previous_contact is None or (
                contact.position_observed_at_ms,
                contact.acquired_at_ms,
            ) > (
                previous_contact.position_observed_at_ms,
                previous_contact.acquired_at_ms,
            ):
                self._contacts[contact.hex] = contact
        return True

    async def _acquire(self, settings: AdsbSettings, generation: int) -> None:
        async with self._lock:
            if generation != self._generation:
                return
            started, attempts = self._monotonic(), self._attempts
            try:
                if settings.mode == "military_and_included":
                    await self._fetch_sources(["military"], generation)
                if generation != self._generation:
                    return
                pending = []
                for hex_code in settings.include_hexes:
                    if hex_code in settings.exclude_hexes:
                        continue
                    contact = self._contacts.get(hex_code)
                    supplied_current = (
                        settings.mode == "military_and_included"
                        and contact is not None
                        and position_state(contact, self._time() * 1000) == "current"
                    )
                    # A retained cached military contact is not evidence that the
                    # current source response supplied a position; fallback is
                    # based on successful source acquisition in this cycle.
                    source = self._sources.get("military")
                    supplied_current = (
                        supplied_current
                        and source is not None
                        and source.error is None
                        and contact.acquired_at_ms == source.last_success_at_ms
                    )
                    if not supplied_current:
                        pending.append(f"hex:{hex_code}")
                # One request for ordinary lists. Sequential minimum chunking
                # respects readsb's documented cap and stops on batch failure.
                limit = AdsbLolProvider.HEX_BATCH_LIMIT
                for offset in range(0, len(pending), limit):
                    if not await self._fetch_sources(
                        pending[offset : offset + limit], generation
                    ):
                        break
                else:
                    if pending:
                        # Earlier successful chunks cannot reset backoff for a
                        # later failing chunk. Recover only after the full batch.
                        self._failures.pop("included", None)
                        self._retry.pop("included", None)
                if generation == self._generation:
                    self._prune(settings)
            finally:
                if self._attempts != attempts:
                    finished = self._monotonic()
                    self._next_cycle = (
                        started + 15 if finished - started < 15 else finished + 15
                    )
