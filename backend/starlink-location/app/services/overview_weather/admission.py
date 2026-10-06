"""Shared rolling budgets and bounded priority admission for one worker."""

import asyncio
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass

from .clock import WeatherClock
from .protocol import WeatherUnavailable, remaining


@dataclass
class Ticket:
    future: asyncio.Future
    detail: bool
    granted: bool = False


class WeatherAdmission:
    def __init__(self, clock: WeatherClock):
        self.clock = clock
        self._attempts: deque[float] = deque()
        self._detail_attempts: deque[float] = deque()
        self._waiting: list[Ticket] = []
        self._active = 0
        self._detail_active = 0

    @property
    def _pending(self):
        return len(self._waiting)

    def take_attempt(self, *, detail: bool = False) -> None:
        now = self.clock.monotonic()
        for history in (self._attempts, self._detail_attempts):
            while history and history[0] <= now - 60:
                history.popleft()
        if len(self._attempts) >= 90 or (detail and len(self._detail_attempts) >= 30):
            raise WeatherUnavailable()
        self._attempts.append(now)
        if detail:
            self._detail_attempts.append(now)

    def _drain(self):
        while self._active < 4:
            eligible = [
                ticket
                for ticket in self._waiting
                if not ticket.future.done()
                and (not ticket.detail or self._detail_active < 2)
            ]
            if not eligible:
                break
            ticket = next((item for item in eligible if not item.detail), eligible[0])
            self._waiting.remove(ticket)
            ticket.granted = True
            self._active += 1
            self._detail_active += ticket.detail
            ticket.future.set_result(None)

    @asynccontextmanager
    async def admit(self, deadline: float, *, detail: bool = False):
        if self._pending >= 32:
            raise WeatherUnavailable()
        ticket = Ticket(asyncio.get_running_loop().create_future(), detail)
        self._waiting.append(ticket)
        self._drain()
        try:
            async with asyncio.timeout(remaining(deadline, self.clock)):
                await ticket.future
            yield
        except TimeoutError as error:
            raise WeatherUnavailable() from error
        finally:
            if ticket in self._waiting:
                self._waiting.remove(ticket)
            if ticket.granted:
                self._active -= 1
                self._detail_active -= ticket.detail
            self._drain()
