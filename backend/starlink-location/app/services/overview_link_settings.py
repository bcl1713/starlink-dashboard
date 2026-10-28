import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from filelock import FileLock

from app.models.overview_presets import PresetWeatherVisibility


@dataclass(frozen=True)
class OverviewLinkSettings:
    """Shared visibility preferences for Overview panels and map layers."""

    starshield_link_enabled: bool = True
    x_band_link_enabled: bool = True
    orbital_traffic_enabled: bool = False
    aircraft_history_enabled: bool = True
    country_borders_enabled: bool = False
    state_borders_enabled: bool = False
    operational_clocks_enabled: bool = True
    arrival_panel_enabled: bool = True
    planned_satellite_panel_enabled: bool = True
    map_status_enabled: bool = True
    legend_enabled: bool = True
    latency_panel_enabled: bool = True
    downlink_panel_enabled: bool = True
    uplink_panel_enabled: bool = True
    packet_loss_panel_enabled: bool = True
    obstruction_panel_enabled: bool = True
    aircraft_marker_enabled: bool = True
    planned_route_enabled: bool = True
    poi_markers_enabled: bool = True
    flight_events_enabled: bool = True
    x_band_events_enabled: bool = True
    ka_events_enabled: bool = True
    starshield_events_enabled: bool = True
    ground_entry_point_enabled: bool = True
    configured_satellites_enabled: bool = True
    next_flight_events_only: bool = False


PRESET_NAMES = ("normal", "communications", "weather", "customer")


class OverviewSettingsConflict(Exception):
    """The supplied baseline no longer matches persisted settings."""


_SETTING_FIELDS = frozenset(OverviewLinkSettings.__dataclass_fields__)


def _validate_fields(payload: object) -> dict[str, bool]:
    """Strictly validate update fields and recognized saved visibility values."""
    if not isinstance(payload, dict):
        raise TypeError("Overview link settings must be an object")
    if payload.keys() - _SETTING_FIELDS:
        raise ValueError("Unknown overview link setting")
    if any(type(value) is not bool for value in payload.values()):
        raise TypeError("Overview link settings must be booleans")
    return payload


def _settings_from_payload(payload: dict[str, object]) -> OverviewLinkSettings:
    """Validate this version's fields, defaulting only those that are absent."""
    known_fields = {
        key: value for key, value in payload.items() if key in _SETTING_FIELDS
    }
    return OverviewLinkSettings(**_validate_fields(known_fields))


class OverviewLinkSettingsStore:
    """Atomically merge installation settings, retaining other versions' fields."""

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
        return _settings_from_payload(self._read_payload())

    def _read_payload(self) -> dict[str, object]:
        """Read the complete saved object without discarding unfamiliar fields."""
        try:
            with self._path.open(encoding="utf-8") as handle:
                payload = json.load(handle)
        except FileNotFoundError:
            return {}
        if not isinstance(payload, dict):
            raise TypeError("Overview link settings must be an object")
        return payload

    def update(
        self, changes: dict[str, bool], expected_values: dict[str, bool] | None = None
    ) -> OverviewLinkSettings:
        """Merge only supplied fields without losing another viewer's edits."""
        changes = _validate_fields(changes)
        if not changes:
            raise ValueError("At least one overview link setting is required")
        if expected_values is not None:
            _validate_fields(expected_values)
            if expected_values.keys() != changes.keys():
                raise ValueError("Expected values must match changed fields")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            payload = self._read_payload()
            current = asdict(_settings_from_payload(payload))
            if expected_values is not None and any(
                current[key] != value for key, value in expected_values.items()
            ):
                raise OverviewSettingsConflict(
                    "Settings changed; refresh before retrying"
                )
            payload.update(current)
            payload.update(changes)
            settings = _settings_from_payload(payload)
            self._write(payload)
            return settings

    def get_presets(self) -> dict:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            return self._presets(self._read_payload())

    @staticmethod
    def _presets(payload: dict) -> dict:
        saved = payload.get("operator_presets", {})
        if not isinstance(saved, dict):
            raise TypeError("Invalid saved presets")
        result = {}
        for name in PRESET_NAMES:
            preset = saved.get(name)
            if preset is not None and (
                not isinstance(preset, dict)
                or type(preset.get("version")) is not int
                or preset["version"] < 1
                or not _validate_fields(preset.get("settings"))
            ):
                raise ValueError("Invalid saved preset")
            if preset is not None and "weather_visibility" in preset:
                PresetWeatherVisibility.model_validate(preset["weather_visibility"])
            result[name] = preset
        return result

    def save_preset(
        self,
        name: str,
        settings: dict[str, bool],
        expected_version: int,
        weather_visibility: dict[str, bool] | None = None,
    ) -> dict:
        if name not in PRESET_NAMES or not _validate_fields(settings):
            raise ValueError("Invalid preset")
        if weather_visibility is not None:
            weather_visibility = PresetWeatherVisibility.model_validate(
                weather_visibility
            ).model_dump()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            payload = self._read_payload()
            _settings_from_payload(payload)
            current = self._presets(payload)[name]
            version = current["version"] if current else 0
            if version != expected_version:
                raise OverviewSettingsConflict(
                    "Preset changed; refresh before retrying"
                )
            preset = {"version": version + 1, "settings": settings}
            if weather_visibility is not None:
                preset["weather_visibility"] = weather_visibility
            payload.setdefault("operator_presets", {})[name] = preset
            self._write(payload)
            return preset

    def _write(self, payload: dict) -> None:
        """Replace the shared file only after flushing the complete new state."""
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
