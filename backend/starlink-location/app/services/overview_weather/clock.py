"""Weather time is independent of the simulation clock."""

import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class WeatherClock:
    utc_ms: Callable[[], int] = lambda: int(time.time() * 1000)
    monotonic: Callable[[], float] = time.monotonic
