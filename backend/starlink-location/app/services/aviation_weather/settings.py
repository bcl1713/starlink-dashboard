"""Atomic, installation-wide default-off aviation preferences."""

import json
import os
import tempfile
from pathlib import Path

from filelock import FileLock
from pydantic import Field

from app.models.aviation_weather import Contract


class AviationSettings(Contract):
    metar: bool = False
    taf: bool = False
    sigmet: bool = False
    revision: int = Field(default=0, ge=0)


class AviationSettingsUpdate(Contract):
    metar: bool | None = None
    taf: bool | None = None
    sigmet: bool | None = None

    def changes(self):
        values = self.model_dump(exclude_unset=True)
        if not values or any(value is None for value in values.values()):
            raise ValueError("At least one boolean preference required")
        return values


class AviationSettingsStore:
    def __init__(self, path: Path):
        self.path = path
        self.lock = FileLock(f"{path}.lock")

    def _read(self):
        try:
            return AviationSettings.model_validate_json(self.path.read_bytes())
        except FileNotFoundError:
            return AviationSettings()

    def get(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock:
            return self._read()

    def update(self, changes: dict):
        changes = AviationSettingsUpdate.model_validate(changes).changes()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock:
            old = self._read()
            values = {**old.model_dump(), **changes}
            if values == old.model_dump():
                return old
            values["revision"] = old.revision + 1
            result = AviationSettings.model_validate(values)
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
            return result
