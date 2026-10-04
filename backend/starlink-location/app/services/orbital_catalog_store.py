"""Crash-safe catalog and fail-closed provider clock under one shared lock."""

import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from filelock import FileLock

from app.services.orbital_catalog_models import utc_epoch

COOLDOWN = timedelta(hours=2)
EMPTY_CATALOG = {
    "generation": "",
    "acquired_at": None,
    "objects": [],
    "rejected_count": 0,
    "truncated_count": 0,
}
EMPTY_STATE = {
    "last_attempt_at": None,
    "retry_after_at": None,
    "suspended": False,
    "provider_error": None,
}


class OrbitalCatalogStore:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.directory = directory
        self._lock = FileLock(str(directory / "orbital.lock"))
        self._catalog = directory / "catalog.json"
        self._state = directory / "provider-state.json"

    def _atomic_write(self, path: Path, payload: dict):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", dir=self.directory, suffix=".tmp", delete=False
            ) as handle:
                temporary = Path(handle.name)
                json.dump(payload, handle, allow_nan=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            descriptor = os.open(self.directory, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def _read_state(self) -> dict:
        try:
            payload = json.loads(self._state.read_text())
            if (
                not isinstance(payload, dict)
                or type(payload.get("suspended")) is not bool
            ):
                raise ValueError("Invalid provider state")
            for key in ("last_attempt_at", "retry_after_at"):
                if key not in payload:
                    raise ValueError("Incomplete provider state")
                if payload[key] is not None:
                    if not isinstance(payload[key], str):
                        raise ValueError("Invalid attempt timestamp")
                    utc_epoch(payload[key])
            return {**EMPTY_STATE, **payload}
        except FileNotFoundError:
            if not self._catalog.exists():
                return EMPTY_STATE.copy()
        except (OSError, ValueError, TypeError):
            pass
        return {
            **EMPTY_STATE,
            "suspended": True,
            "state_corrupt": True,
            "provider_error": "Provider state unreadable; explicit resume required",
        }

    def read_state(self) -> dict:
        with self._lock:
            return self._read_state()

    def reserve_attempt(self, now: datetime) -> bool:
        with self._lock:
            state = self._read_state()
            if state["suspended"]:
                return False
            if (
                state["last_attempt_at"]
                and now < utc_epoch(state["last_attempt_at"]) + COOLDOWN
            ):
                return False
            if state["retry_after_at"] and now < utc_epoch(state["retry_after_at"]):
                return False
            state.update(last_attempt_at=now.isoformat(), provider_error=None)
            self._atomic_write(self._state, state)
            return True

    def record_failure(self, error: str, suspended: bool, retry_after: datetime | None):
        with self._lock:
            state = self._read_state()
            state.update(
                provider_error=error, suspended=state["suspended"] or suspended
            )
            if retry_after is not None:
                previous = state["retry_after_at"]
                if previous is None or retry_after > utc_epoch(previous):
                    state["retry_after_at"] = retry_after.isoformat()
            self._atomic_write(self._state, state)

    def resume(self, now: datetime):
        with self._lock:
            state = self._read_state()
            if state.pop("state_corrupt", False):
                state["last_attempt_at"] = now.isoformat()
                state["retry_after_at"] = (now + COOLDOWN).isoformat()
            state.update(suspended=False, provider_error=None)
            self._atomic_write(self._state, state)

    def read_catalog(self) -> dict:
        with self._lock:
            try:
                payload = json.loads(self._catalog.read_text())
                if not isinstance(payload, dict) or not isinstance(
                    payload.get("objects"), list
                ):
                    raise TypeError("Invalid catalog")
                return {**EMPTY_CATALOG, **payload}
            except (OSError, ValueError, TypeError):
                return EMPTY_CATALOG.copy()

    def save_catalog(self, payload: dict):
        with self._lock:
            self._atomic_write(self._catalog, payload)
