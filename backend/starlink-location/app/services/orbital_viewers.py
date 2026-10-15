"""Bounded visible-viewer demand; no timer is created by this container."""

from datetime import datetime, timedelta


class OrbitalViewers:
    def __init__(self):
        self._leases: dict[str, datetime] = {}

    def prune(self, now: datetime):
        self._leases = {
            key: expiry for key, expiry in self._leases.items() if expiry > now
        }

    def acquire(self, viewer_id: str, now: datetime) -> datetime:
        self.prune(now)
        if viewer_id not in self._leases and len(self._leases) >= 128:
            raise OverflowError("Orbital viewer capacity reached")
        expiry = now + timedelta(seconds=75)
        self._leases[viewer_id] = expiry
        return expiry

    def release(self, viewer_id: str):
        self._leases.pop(viewer_id, None)

    def valid(self, viewer_id: str, now: datetime) -> bool:
        self.prune(now)
        return viewer_id in self._leases

    def count(self, now: datetime) -> int:
        self.prune(now)
        return len(self._leases)

    def next_expiry(self, now: datetime) -> datetime | None:
        self.prune(now)
        return min(self._leases.values(), default=None)
