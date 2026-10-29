"""Atomic, installation-wide default-off aviation preferences."""

import json
import os
import tempfile
from pathlib import Path

from filelock import FileLock
from pydantic import Field

from app.models.aviation_grid import GfsSelection
from app.models.aviation_weather import Contract
from app.services.settings_conflict import SettingsConflict


class AviationSettings(Contract):
    metar: bool = False
    taf: bool = False
    departure_weather: bool = False
    arrival_weather: bool = False
    sigmet: bool = False
    sigmet_intersecting_only: bool = False
    winds: bool = False
    temperature: bool = False
    gfs_selection: GfsSelection = Field(default_factory=GfsSelection)
    revision: int = Field(default=0, ge=0)


class AviationSettingsUpdate(Contract):
    expected_revision: int | None = Field(default=None, ge=0, strict=True)
    metar: bool | None = None
    taf: bool | None = None
    departure_weather: bool | None = None
    arrival_weather: bool | None = None
    sigmet: bool | None = None
    sigmet_intersecting_only: bool | None = None
    winds: bool | None = None
    temperature: bool | None = None
    gfs_selection: GfsSelection | None = None

    def changes(self):
        values = self.model_dump(exclude_unset=True)
        if not (values.keys() - {"expected_revision"}) or any(
            value is None for value in values.values()
        ):
            raise ValueError("At least one weather preference required")
        if values.get("winds") and values.get("temperature"):
            raise ValueError("Only one GFS layer may be enabled")
        return values


def effective_settings(settings: AviationSettings) -> AviationSettings:
    """Legacy simultaneous layers resolve to wind, without changing revision."""
    if settings.winds and settings.temperature:
        return settings.model_copy(update={"temperature": False})
    return settings


class AviationSettingsStore:
    def __init__(self, path: Path, *, readonly=False):
        self.path = path
        self.readonly = readonly
        self.lock = FileLock(f"{path}.lock")

    def _read(self):
        try:
            return AviationSettings.model_validate_json(self.path.read_bytes())
        except FileNotFoundError:
            return AviationSettings()

    def get(self, *, timeout=None):
        """Read preferences, optionally bounding this caller's lock wait.

        Omitted timeout preserves the store's existing blocking semantics.
        """
        if self.readonly:
            return effective_settings(self._read())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock.acquire(timeout=timeout):
            return effective_settings(self._read())

    def repair_legacy(self) -> tuple[AviationSettings, bool]:
        """Writable owner calls this while holding its outer GFS control lock."""
        if self.readonly:
            raise RuntimeError("Scientific worker settings are read-only")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock:
            old = self._read()
            result = effective_settings(old)
            if result == old:
                return old, False
            result = result.model_copy(update={"revision": old.revision + 1})
            self._write(result)
            return result, True

    def update(self, changes: dict):
        if self.readonly:
            raise RuntimeError("Scientific worker settings are read-only")
        changes = AviationSettingsUpdate.model_validate(changes).changes()
        expected_revision = changes.pop("expected_revision", None)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock:
            old = self._read()
            if expected_revision is not None and expected_revision != old.revision:
                raise SettingsConflict(
                    "Aviation visibility changed; refresh before retrying"
                )
            values = {**effective_settings(old).model_dump(), **changes}
            if changes.get("winds"):
                values["temperature"] = False
            elif changes.get("temperature"):
                values["winds"] = False
            if values == old.model_dump():
                return old
            values["revision"] = old.revision + 1
            result = AviationSettings.model_validate(values)
            self._write(result)
            return result

    def _write(self, result: AviationSettings) -> None:
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
                encoding="utf-8",
            ) as stream:
                temporary = Path(stream.name)
                json.dump(result.model_dump(), stream)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def layer_enabled(settings: AviationSettings, layer: str) -> bool:
    """Airfield visibility requires both terminal products without global markers."""
    return bool(
        getattr(settings, layer)
        or (
            layer in {"metar", "taf"}
            and (settings.departure_weather or settings.arrival_weather)
        )
    )
