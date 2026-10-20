"""Explicit wall and monotonic clock dependencies for Operator services."""

import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...

    def monotonic(self) -> float: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def monotonic(self) -> float:
        return time.monotonic()


def observation_now(clock: Clock) -> datetime:
    """Age physical observations and durable writes independently of replay time."""
    return getattr(clock, "observation_now", clock.now)()


class MissionClock:
    """Use mission time for schedules, real time for observation age and expiry."""

    def __init__(
        self,
        mission_now: Callable[[], datetime | None],
        *,
        observation_clock: Clock | None = None,
    ):
        self._mission_now = mission_now
        self._observation_clock = observation_clock or SystemClock()

    def now(self) -> datetime:
        return self._mission_now() or self.observation_now()

    def observation_now(self) -> datetime:
        return self._observation_clock.now()

    def monotonic(self) -> float:
        return self._observation_clock.monotonic()
