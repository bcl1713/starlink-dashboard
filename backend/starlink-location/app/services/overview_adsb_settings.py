"""Atomic installation-wide settings; live aircraft positions are never persisted."""

import json
import os
import tempfile
from pathlib import Path

from app.models.overview_adsb import AdsbSettings, AdsbSettingsUpdate
from filelock import FileLock


class AdsbSettingsStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = FileLock(f"{path}.lock")

    def _read(self) -> AdsbSettings:
        try:
            with self._path.open(encoding="utf-8") as handle:
                payload = json.load(handle)
        except FileNotFoundError:
            return AdsbSettings()
        return AdsbSettings.model_validate(payload)

    def get(self) -> AdsbSettings:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            return self._read()

    def update(self, changes: dict[str, object]) -> AdsbSettings:
        validated = AdsbSettingsUpdate.model_validate(changes)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            old = self._read()
            payload = old.model_dump()
            payload.update(validated.model_dump(exclude_unset=True))
            payload["revision"] = old.revision + 1
            settings = AdsbSettings.model_validate(payload)
            temporary: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    dir=self._path.parent,
                    prefix=f".{self._path.name}.",
                    suffix=".tmp",
                    encoding="utf-8",
                    delete=False,
                ) as handle:
                    temporary = Path(handle.name)
                    json.dump(settings.model_dump(), handle)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self._path)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            return settings
