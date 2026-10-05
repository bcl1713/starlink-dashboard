"""One worker's rolling attempt budget and bounded admission queue."""

import asyncio
from collections import deque
from contextlib import asynccontextmanager

from .clock import WeatherClock
from .protocol import WeatherUnavailable, remaining


class WeatherAdmission:
    def __init__(self, clock: WeatherClock):
        self.clock = clock
        self._attempts: deque[float] = deque()
        self._semaphore = asyncio.Semaphore(4)
        self._pending = 0

    def take_attempt(self) -> None:
        now = self.clock.monotonic()
        while self._attempts and self._attempts[0] <= now - 60:
            self._attempts.popleft()
        if len(self._attempts) >= 90:
            raise WeatherUnavailable()
        self._attempts.append(now)

    @asynccontextmanager
    async def admit(self, deadline: float):
        if self._pending >= 32:
            raise WeatherUnavailable()
        self._pending += 1
        try:
            async with asyncio.timeout(remaining(deadline, self.clock)):
                await self._semaphore.acquire()
        except TimeoutError as error:
            raise WeatherUnavailable() from error
        finally:
            self._pending -= 1
        try:
            yield
        finally:
            self._semaphore.release()
