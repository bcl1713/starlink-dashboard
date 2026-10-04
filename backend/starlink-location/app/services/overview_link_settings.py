import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from filelock import FileLock


@dataclass(frozen=True)
class OverviewLinkSettings:
    """Shared visibility preferences for the Overview data links and experimental orbital view."""

    starshield_link_enabled: bool = True
    x_band_link_enabled: bool = True
    orbital_traffic_enabled: bool = False


_SETTING_FIELDS = frozenset(OverviewLinkSettings.__dataclass_fields__)


def _validate_fields(payload: object) -> dict[str, bool]:
    """Reject malformed settings instead of coercing saved visibility values."""
    if not isinstance(payload, dict):
        raise TypeError("Overview link settings must be an object")
    if payload.keys() - _SETTING_FIELDS:
        raise ValueError("Unknown overview link setting")
    if any(type(value) is not bool for value in payload.values()):
        raise TypeError("Overview link settings must be booleans")
    return payload


class OverviewLinkSettingsStore:
    """Read and atomically merge installation settings under a shared file lock."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = FileLock(f"{path}.lock")

    def get(self) -> OverviewLinkSettings:
        """Return saved settings, defaulting only absent files or fields."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            return self._read()

    def _read(self) -> OverviewLinkSettings:
        """Read settings while the caller holds the file lock."""
        try:
            with self._path.open(encoding="utf-8") as handle:
                payload = json.load(handle)
        except FileNotFoundError:
            return OverviewLinkSettings()
        return OverviewLinkSettings(**_validate_fields(payload))

    def update(self, changes: dict[str, bool]) -> OverviewLinkSettings:
        """Merge only supplied fields without losing another viewer's edits."""
        changes = _validate_fields(changes)
        if not changes:
            raise ValueError("At least one overview link setting is required")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            payload = asdict(self._read())
            payload.update(changes)
            settings = OverviewLinkSettings(**payload)
            temporary_path: Path | None = None
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
                    json.dump(payload, handle)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary_path, self._path)
            finally:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)
            return settings
