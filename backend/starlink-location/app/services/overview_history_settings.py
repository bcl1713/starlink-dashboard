import json
import os
import tempfile
from pathlib import Path

from filelock import FileLock


class OverviewHistorySettingsStore:
    """Store the dashboard-selected Prometheus query window durably."""

    def __init__(self, path: Path, *, default_window_seconds: int) -> None:
        self._path = path
        self._lock = FileLock(f"{path}.lock")
        self._default_window_seconds = self._validate_window_seconds(
            default_window_seconds
        )

    def get_window_seconds(self) -> int:
        """Return the persisted window, or the configured startup default."""
        with self._lock:
            if not self._path.exists():
                return self._default_window_seconds
            with self._path.open() as handle:
                payload = json.load(handle)
        return self._validate_window_seconds(payload["window_seconds"])

    def set_window_seconds(self, window_seconds: int) -> None:
        """Persist a validated dashboard-selected query window atomically."""
        payload = {
            "window_seconds": self._validate_window_seconds(window_seconds),
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            descriptor, temporary_path = tempfile.mkstemp(
                dir=self._path.parent,
                prefix=f"{self._path.name}.",
                suffix=".tmp",
            )
            try:
                with os.fdopen(descriptor, "w") as handle:
                    json.dump(payload, handle)
                    handle.write("\n")
                os.replace(temporary_path, self._path)
            finally:
                Path(temporary_path).unlink(missing_ok=True)

    @staticmethod
    def _validate_window_seconds(window_seconds: int) -> int:
        """Reject non-positive query windows."""
        if isinstance(window_seconds, bool) or window_seconds <= 0:
            raise ValueError("History window must be positive")
        return window_seconds
