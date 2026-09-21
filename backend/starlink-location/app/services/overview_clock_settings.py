import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.services.overview_clock_location import ClockLocation

DEFAULT_OVERVIEW_CLOCKS = (
    ClockLocation(
        label="Zulu / UTC",
        time_zone="UTC",
    ),
    ClockLocation(
        label="Washington, DC",
        time_zone="America/New_York",
    ),
    ClockLocation(
        label="Omaha, NE",
        time_zone="America/Chicago",
    ),
    ClockLocation(
        label="Tokyo, JP",
        time_zone="Asia/Tokyo",
    ),
)


def _parse_clocks(payload: object) -> list[ClockLocation]:
    """Validate a persisted clock payload and return its four clock records."""
    if not isinstance(payload, Mapping):
        raise TypeError("Clock settings must be a mapping")
    clock_records = payload.get("clocks")
    if not isinstance(clock_records, list) or len(clock_records) != len(
        DEFAULT_OVERVIEW_CLOCKS
    ):
        raise ValueError("Exactly four clocks are required")

    clocks = []
    for clock_record in clock_records:
        if not isinstance(clock_record, Mapping):
            raise TypeError("Clock settings entries must be mappings")
        label = clock_record.get("label")
        time_zone = clock_record.get("time_zone")
        if not isinstance(label, str) or not label.strip():
            raise ValueError("Clock labels must not be blank")
        if not isinstance(time_zone, str):
            raise TypeError("Clock time zones must be strings")
        try:
            ZoneInfo(time_zone)
        except (TypeError, ValueError, ZoneInfoNotFoundError) as error:
            raise ValueError("Invalid IANA timezone") from error
        clocks.append(ClockLocation(label=label, time_zone=time_zone))
    return clocks


class OverviewClockSettingsStore:
    """Own persistent operational-clock preferenes."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def get_clocks(self) -> list[ClockLocation]:
        """Return the saved clocks, or the four operational defaults."""
        if not self._path.exists():
            return list(DEFAULT_OVERVIEW_CLOCKS)
        try:
            with self._path.open() as handle:
                return _parse_clocks(json.load(handle))
        except (
            AttributeError,
            json.JSONDecodeError,
            KeyError,
            OSError,
            TypeError,
            ValueError,
            ZoneInfoNotFoundError,
        ):
            return list(DEFAULT_OVERVIEW_CLOCKS)

    def set_clocks(self, clocks: list[ClockLocation]) -> None:
        """Persist the complete editable operational-clock collection."""
        if len(clocks) != len(DEFAULT_OVERVIEW_CLOCKS):
            raise ValueError("Exactly four clocks are required")
        try:
            clocks = _parse_clocks(
                {
                    "clocks": [
                        {
                            "label": clock.label,
                            "time_zone": clock.time_zone,
                        }
                        for clock in clocks
                    ]
                }
            )
        except (AttributeError, TypeError) as error:
            raise ValueError("Invalid clock settings") from error
        self._path.parent.mkdir(parents=True, exist_ok=True)
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
                json.dump(
                    {
                        "clocks": [
                            {
                                "label": clock.label,
                                "time_zone": clock.time_zone,
                            }
                            for clock in clocks
                        ]
                    },
                    handle,
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self._path)
        except Exception:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise
