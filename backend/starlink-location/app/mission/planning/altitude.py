"""Unit defaults apply only at new source intake, never historical loading."""

import re

UNITS = {
    "fl": "flight_level",
    "ft": "feet",
    "feet": "feet",
    "m": "meters",
    "meters": "meters",
}


def parse_altitude(text):
    match = re.fullmatch(
        r"\s*(?:(FL)\s*)?(\d+(?:\.\d+)?)\s*(FL|ft|feet|m|meters)?\s*",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None, None
    prefix, value, suffix = match.groups()
    if prefix and suffix and suffix.lower() != "fl":
        return None, None
    unit = UNITS[(prefix or suffix).lower()] if prefix or suffix else None
    return float(value), unit


def apply_import_units(rows, default_units="flight_level"):
    if default_units not in UNITS.values():
        raise ValueError("Unsupported import altitude units")
    return [
        (
            row.model_copy(
                deep=True,
                update={
                    "confirmed_units": default_units,
                    "unit_origin": "import_default",
                },
            )
            if row.confirmed_units is None and row.source_altitude is not None
            else row.model_copy(deep=True)
        )
        for row in rows
    ]
