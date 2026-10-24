"""Optional, calculation-free notifications at existing mutation boundaries."""

from collections.abc import Callable
from functools import wraps


class MetricsChangeSource:
    """One lifespan-owned subscriber; managers remain usable without metrics."""

    _metrics_change_callback: Callable[[str], None] | None = None

    def set_metrics_change_callback(self, callback: Callable[[str], None] | None):
        self._metrics_change_callback = callback

    def _notify_metrics_changed(self, reason: str):
        if self._metrics_change_callback is not None:
            self._metrics_change_callback(reason)


def metrics_changed(reason: str, *, key: str | None = None):
    """Call inside repository admission, after releasing component-local locks.

    A cheap optional key omits detection/countdown-only changes. Finally also
    invalidates in-memory changes when an existing mutator raises partway through.
    No callback reads a manager, calculates a value, or publishes a frame.
    """

    def decorate(function):
        @wraps(function)
        def changed(self, *args, **kwargs):
            subscribed = self._metrics_change_callback is not None
            before = getattr(self, key)() if subscribed and key else None
            try:
                return function(self, *args, **kwargs)
            finally:
                if subscribed and (key is None or before != getattr(self, key)()):
                    self._notify_metrics_changed(reason)

        return changed

    return decorate


# Persistence operations have no lifespan manager of their own. One detachable
# subscriber covers their existing commit/compensation boundaries, without reads.
mission_metrics_changes = MetricsChangeSource()


def mission_metrics_changed(reason):
    def decorate(function):
        @wraps(function)
        def changed(*args, **kwargs):
            try:
                return function(*args, **kwargs)
            finally:
                mission_metrics_changes._notify_metrics_changed(reason)

        return changed

    return decorate
