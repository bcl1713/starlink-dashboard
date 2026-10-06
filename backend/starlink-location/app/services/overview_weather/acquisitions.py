"""Coalesced subscriber leases, generation fences and bounded success caches."""

import asyncio
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

from .admission import WeatherAdmission
from .clock import WeatherClock
from .protocol import WeatherPayload, WeatherUnavailable
from .transport import PinnedWeatherTransport

Key = tuple[str, str, int, int, int, int]


@dataclass
class Acquisition:
    task: asyncio.Task[WeatherPayload]
    subscribers: int = 0


class WeatherAcquisitionPool:
    def __init__(
        self,
        transport: PinnedWeatherTransport,
        admission: WeatherAdmission,
        clock: WeatherClock,
    ):
        self.transport, self.admission, self.clock = transport, admission, clock
        self._tasks: dict[Key, Acquisition] = {}
        self._cache: OrderedDict[Key, tuple[float, WeatherPayload]] = OrderedDict()
        self._failures: dict[Key, tuple[float, int]] = {}
        self._generation = 0
        self._closed = False
        self._closing: asyncio.Task[None] | None = None

    async def acquire(
        self,
        key: Key,
        url: str,
        max_bytes: int,
        expected_type: str,
        ttl_seconds: float,
        validate: Callable[[bytes], None],
    ) -> WeatherPayload:
        if self._closed:
            raise WeatherUnavailable()
        now = self.clock.monotonic()
        cached = self._cache.get(key)
        if cached is not None:
            if now < cached[0]:
                self._cache.move_to_end(key)
                return cached[1]
            del self._cache[key]
        failed = self._failures.get(key)
        if failed and now < failed[0]:
            raise WeatherUnavailable(int(failed[0] - now + 1))
        acquisition = self._tasks.get(key)
        if acquisition is None:
            if len(self._tasks) >= 36:
                raise WeatherUnavailable()
            generation = self._generation
            deadline = now + 5
            task = asyncio.create_task(
                self._run(
                    key,
                    url,
                    max_bytes,
                    expected_type,
                    ttl_seconds,
                    validate,
                    generation,
                    deadline,
                )
            )
            acquisition = Acquisition(task)
            self._tasks[key] = acquisition
        acquisition.subscribers += 1
        try:
            return await asyncio.shield(acquisition.task)
        except asyncio.CancelledError:
            if asyncio.current_task().cancelling():
                raise
            raise WeatherUnavailable() from None
        finally:
            acquisition.subscribers -= 1
            if acquisition.subscribers == 0:
                if self._tasks.get(key) is acquisition:
                    del self._tasks[key]
                if not acquisition.task.done():
                    acquisition.task.cancel()
                await asyncio.shield(
                    asyncio.gather(acquisition.task, return_exceptions=True)
                )

    async def _run(
        self, key, url, max_bytes, expected_type, ttl, validate, generation, deadline
    ):
        try:
            detail = key[-3] > 2
            async with self.admission.admit(deadline, detail=detail):
                payload = await self.transport.fetch(
                    url,
                    max_bytes,
                    expected_type,
                    deadline,
                    before_attempt=lambda: self.admission.take_attempt(detail=detail),
                )
            validate(payload.body)
            if generation != self._generation or self._closed:
                raise WeatherUnavailable()
            self._cache[key] = (self.clock.monotonic() + ttl, payload)
            self._cache.move_to_end(key)
            self._failures.pop(key, None)
            self._evict()
            return payload
        except (WeatherUnavailable, ValueError, TypeError) as error:
            delay = (
                error.retry_after_seconds
                if isinstance(error, WeatherUnavailable)
                else 30
            )
            if generation == self._generation and not self._closed:
                self._failures[key] = (self.clock.monotonic() + delay, delay)
            raise WeatherUnavailable(delay) from None

    def _evict(self):
        def png_entries():
            return [
                (key, value)
                for key, value in self._cache.items()
                if key[-5] != "metadata"
            ]

        entries = png_entries()
        while (
            len(entries) > 48
            or sum(len(value[1].body) for _, value in entries) > 64 * 1024 * 1024
        ):
            del self._cache[entries[0][0]]
            entries = png_entries()

    async def prune(self, allowed: Callable[[Key], bool]) -> None:
        for key in list(self._cache):
            if not allowed(key):
                del self._cache[key]
        for key in list(self._failures):
            if not allowed(key):
                del self._failures[key]
        removed = []
        for key, acquisition in list(self._tasks.items()):
            if not allowed(key):
                self._tasks.pop(key)
                acquisition.task.cancel()
                removed.append(acquisition.task)
        await asyncio.gather(*removed, return_exceptions=True)

    async def invalidate(self) -> None:
        self._generation += 1
        self._cache.clear()
        self._failures.clear()
        tasks = [item.task for item in self._tasks.values()]
        self._tasks.clear()
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def aclose(self) -> None:
        if self._closing is None:
            self._closed = True
            self._closing = asyncio.create_task(self.invalidate())
        await asyncio.shield(self._closing)
