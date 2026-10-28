"""Lifecycle ownership of current mission gauges, separate from aggregates."""

from threading import RLock


class MissionMetrics:
    """One owner and one scrape snapshot across all native mission gauges.

    Writers take repository admission before this short lock. Collection only
    takes this lock while copying native metric families, then releases it before
    exposition. The registry is never mutated after registration. Native Gauge
    removal uses public APIs and runs only on identity changes/explicit clears.
    """

    def __init__(self, active, *gauges):
        self.active = active
        self.gauges = (active, *gauges)
        self._lock = RLock()
        self._owner = None

    def describe(self):
        for gauge in self.gauges:
            yield from gauge.describe()

    def collect(self):
        with self._lock:
            families = [family for gauge in self.gauges for family in gauge.collect()]
        yield from families

    def _remove(self, mission_id=None):
        for gauge in self.gauges:
            for family in gauge.collect():
                for sample in family.samples:
                    if mission_id is None or sample.labels["mission_id"] == mission_id:
                        labels = (sample.labels["mission_id"],) + tuple(
                            sample.labels[key]
                            for key in ("route_id", "transport")
                            if key in sample.labels
                        )
                        gauge.remove(*labels)

    def activate(self, mission_id, route_id):
        with self._lock:
            owner = (mission_id, route_id)
            if owner != self._owner:
                self._remove()
                self._owner = owner
            self.active.labels(mission_id=mission_id, route_id=route_id).set(1)

    def clear(self, mission_id):
        with self._lock:
            self._remove(mission_id)
            if self._owner is not None and self._owner[0] == mission_id:
                self._owner = None

    def clear_current(self):
        with self._lock:
            if self._owner is not None:
                self._remove()
                self._owner = None

    def invalidate(self, mission_id, route_id):
        """A committed owner is known, but its dynamic values are unavailable."""
        with self._lock:
            self._remove()
            self._owner = None
            self.activate(mission_id, route_id)

    def update(self, mission_id, values):
        with self._lock:
            if self._owner is None or self._owner[0] != mission_id:
                return
            for gauge, labels, value in values:
                gauge.labels(*labels).set(value)

    def publish(self, mission_id, route_id, values):
        with self._lock:
            self.activate(mission_id, route_id)
            self.update(mission_id, values)
