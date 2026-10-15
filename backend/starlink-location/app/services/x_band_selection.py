"""Persistent manual planning selection, independent of mission ownership."""

import json
import os
import tempfile
from pathlib import Path

from filelock import FileLock


class XBandSelectionStore:
    """Store one nullable satellite ID with atomic, confirmed saves."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = FileLock(f"{path}.lock", timeout=5)

    def _read(self) -> str | None:
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        if not isinstance(payload, dict):
            raise TypeError("Satellite selection must be an object")
        satellite_id = payload.get("satellite_id")
        if satellite_id is not None and (
            not isinstance(satellite_id, str) or not satellite_id.strip()
        ):
            raise ValueError("Satellite selection must be a nonempty ID or null")
        return satellite_id

    def get(self) -> str | None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            return self._read()

    def update(self, satellite_id: str | None) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            # Do not overwrite unreadable settings with an apparently successful save.
            self._read()
            temporary_path = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    dir=self._path.parent,
                    prefix=f".{self._path.name}.",
                    suffix=".tmp",
                    encoding="utf-8",
                    delete=False,
                ) as handle:
                    temporary_path = Path(handle.name)
                    json.dump({"satellite_id": satellite_id}, handle)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary_path, self._path)
            finally:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)
