"""Atomic installation-wide switch; reads and construction never acquire weather."""

import json
import os
import tempfile
from pathlib import Path

from app.models.overview_weather import WeatherSettings, WeatherSettingsUpdate
from filelock import FileLock


class WeatherSettingsStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = FileLock(f"{path}.lock")

    def _read(self) -> WeatherSettings:
        try:
            with self._path.open(encoding="utf-8") as handle:
                return WeatherSettings.model_validate(json.load(handle))
        except FileNotFoundError:
            return WeatherSettings()

    def get(self) -> WeatherSettings:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            return self._read()

    def update(self, changes: dict[str, object]) -> WeatherSettings:
        validated = WeatherSettingsUpdate.model_validate(changes)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            old = self._read()
            if old.enabled == validated.enabled:
                return old
            settings = WeatherSettings(
                enabled=validated.enabled, revision=old.revision + 1
            )
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
