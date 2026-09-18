from collections.abc import Mapping

import reverse_geocoder
from timezonefinder import TimezoneFinder

US_STATE_ABBREVIATIONS = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virginia": "VA",
    "Washington": "WA",
    "Washington, D.C.": "DC",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
}

US_LOCALITY_NAME_OVERRIDES = {
    "Washington, D.C.": "Washington",
}


class OfflineClockGeography:
    """Resolve endpoint geography with packaged offline data."""

    def __init__(self) -> None:
        self._time_zone_finder = TimezoneFinder()

    def time_zone_at(self, latitude: float, longitude: float) -> str | None:
        return self._time_zone_finder.timezone_at_land(
            lat=latitude,
            lng=longitude,
        )

    def locality_at(
        self,
        latitude: float,
        longitude: float,
    ) -> Mapping[str, str] | None:
        locality = reverse_geocoder.search((latitude, longitude))[0]
        raw_city = locality["name"]
        raw_country_code = locality["cc"]
        raw_admin1 = locality["admin1"]
        if (
            not isinstance(raw_city, str)
            or not isinstance(raw_country_code, str)
            or not isinstance(raw_admin1, str)
        ):
            return None
        admin1 = raw_admin1
        if raw_country_code == "US":
            admin1 = US_STATE_ABBREVIATIONS.get(raw_admin1)
            if admin1 is None:
                return None
        city = US_LOCALITY_NAME_OVERRIDES.get(raw_city, raw_city)
        return {
            "city": city,
            "country_code": raw_country_code,
            "admin1": admin1,
        }
