import json
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
        with self._path.open() as handle:
            payload = json.load(handle)
        return [
            ClockLocation(
                label=clock["label"],
                time_zone=clock["time_zone"],
            )
            for clock in payload["clocks"]
        ]

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
        with self._path.open("w") as handle:
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
