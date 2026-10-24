"""Shared manual destination settings and packaged airport lookup."""

import gzip
import json
import os
import tempfile
import unicodedata
from functools import lru_cache
from pathlib import Path

from filelock import FileLock
from pydantic import BaseModel, ConfigDict, Field


class ManualDestination(BaseModel):
    """A complete operator-selected point, independent of mission lifecycle."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False, strict=True)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False, strict=True)
    airport_code: str | None = Field(default=None, min_length=1, max_length=12)


class ManualDestinationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    destination: ManualDestination | None


class ManualDestinationStore:
    """Validate complete replacements before an atomic, locked file write."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = FileLock(f"{path}.lock")

    def get(self) -> ManualDestinationSettings:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            try:
                return ManualDestinationSettings.model_validate_json(
                    self._path.read_text()
                )
            except FileNotFoundError:
                return ManualDestinationSettings(destination=None)

    def set(self, settings: ManualDestinationSettings) -> ManualDestinationSettings:
        settings = ManualDestinationSettings.model_validate(settings.model_dump())
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
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
                    handle.write(settings.model_dump_json() + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary_path, self._path)
            finally:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)
        return settings


def _normalize(value: str) -> str:
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(c)
    )


@lru_cache(maxsize=1)
def _airports() -> tuple:
    with gzip.open(
        Path(__file__).parents[1] / "assets" / "airports.json.gz",
        "rt",
        encoding="utf-8",
    ) as handle:
        return tuple(
            (
                a,
                _normalize(
                    " ".join(
                        a.get(key) or ""
                        for key in (
                            "ident",
                            "name",
                            "icao_code",
                            "iata_code",
                            "gps_code",
                            "local_code",
                            "municipality",
                            "country",
                        )
                    )
                ),
            )
            for a in json.load(handle)
        )


def search_airports(query: str) -> list[dict]:
    query = _normalize(query.strip())
    if len(query) < 2:
        return []
    matches = [
        (a, text)
        for a, text in _airports()
        if all(word in text for word in query.split())
    ]
    matches.sort(
        key=lambda item: (
            (
                0
                if query
                in [
                    _normalize(item[0].get(k) or "")
                    for k in (
                        "ident",
                        "icao_code",
                        "iata_code",
                        "gps_code",
                        "local_code",
                    )
                ]
                else 1
            ),
            item[0]["name"],
            item[0]["ident"],
        )
    )
    return [a for a, _ in matches[:20]]
