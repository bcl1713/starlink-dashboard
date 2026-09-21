import json
import os
import tempfile
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
                payload = json.load(handle)
            clocks = [
                ClockLocation(
                    label=clock["label"],
                    time_zone=clock["time_zone"],
                )
                for clock in payload["clocks"]
            ]
        except (json.JSONDecodeError, KeyError, OSError, TypeError):
            return list(DEFAULT_OVERVIEW_CLOCKS)
        if len(clocks) != len(DEFAULT_OVERVIEW_CLOCKS):
            return list(DEFAULT_OVERVIEW_CLOCKS)
        return clocks

    def set_clocks(self, clocks: list[ClockLocation]) -> None:
        """Persist the complete editable operational-clock collection."""
        if len(clocks) != len(DEFAULT_OVERVIEW_CLOCKS):
            raise ValueError("Exactly four clocks are required")
        for clock in clocks:
            if not clock.label.strip():
                raise ValueError("Clock labels must not be blank")
            try:
                ZoneInfo(clock.time_zone)
            except ZoneInfoNotFoundError as error:
                raise ValueError("Invalid IANA timezone") from error
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
