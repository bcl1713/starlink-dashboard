"""Bounded, canonical OMM elements and independent epoch eligibility."""

import hashlib
import json
import math
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

MAX_OBJECTS = 16384
EARTH_RADIUS_KM = 6378.137
NUMERIC_FIELDS = (
    "MEAN_MOTION",
    "ECCENTRICITY",
    "INCLINATION",
    "RA_OF_ASC_NODE",
    "ARG_OF_PERICENTER",
    "MEAN_ANOMALY",
    "BSTAR",
    "MEAN_MOTION_DOT",
    "MEAN_MOTION_DDOT",
)
METADATA_DEFAULTS = {
    "CENTER_NAME": "EARTH",
    "REF_FRAME": "TEME",
    "TIME_SYSTEM": "UTC",
    "MEAN_ELEMENT_THEORY": "SGP4",
}


def utc_epoch(value: str) -> datetime:
    instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    # CelesTrak JSON omits the redundant TIME_SYSTEM=UTC field and UTC zone.
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(timezone.utc)


def _catalog_id(value: object) -> str:
    if type(value) is int:
        value = str(value)
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,9}", value):
        raise ValueError("Invalid decimal catalog ID")
    if int(value) <= 0:
        raise ValueError("Invalid catalog ID")
    return str(int(value))


def _validate_object(raw: object) -> dict:
    if not isinstance(raw, dict):
        raise TypeError("OMM must be an object")
    obj = {"NORAD_CAT_ID": _catalog_id(raw.get("NORAD_CAT_ID"))}
    if not isinstance(raw.get("EPOCH"), str):
        raise TypeError("Missing UTC epoch")
    obj["EPOCH"] = utc_epoch(raw["EPOCH"]).isoformat().replace("+00:00", "Z")
    for field, expected in METADATA_DEFAULTS.items():
        if raw.get(field, expected) != expected:
            raise ValueError("Unsupported OMM metadata")
    for field in NUMERIC_FIELDS:
        value = raw.get(field)
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("Missing or nonfinite mean element")
        obj[field] = float(value)
    if not (0 < obj["MEAN_MOTION"] <= 18 and 0 <= obj["ECCENTRICITY"] < 1):
        raise ValueError("Invalid orbit")
    if not 0 <= obj["INCLINATION"] <= 180:
        raise ValueError("Invalid inclination")
    if any(
        not 0 <= obj[field] < 360
        for field in ("RA_OF_ASC_NODE", "ARG_OF_PERICENTER", "MEAN_ANOMALY")
    ):
        raise ValueError("Invalid orbital angle")
    angular_rate = obj["MEAN_MOTION"] * 2 * math.pi / 86400
    perigee = (398600.4418 / angular_rate**2) ** (1 / 3) * (1 - obj["ECCENTRICITY"])
    if perigee <= EARTH_RADIUS_KM:
        raise ValueError("Orbit intersects Earth")
    return obj


def validate_catalog(payload: object) -> dict:
    if not isinstance(payload, list) or not payload:
        raise ValueError("Empty or malformed catalog")
    ids = []
    for obj in payload:
        try:
            ids.append(_catalog_id(obj.get("NORAD_CAT_ID")))
        except (AttributeError, ValueError):
            pass
    counts = Counter(ids)
    accepted = []
    rejected = 0
    for raw in payload:
        try:
            obj = _validate_object(raw)
            if counts[obj["NORAD_CAT_ID"]] != 1:
                raise ValueError("Ambiguous duplicate ID")
            accepted.append(obj)
        except (ValueError, TypeError, OverflowError):
            rejected += 1
    accepted.sort(key=lambda obj: int(obj["NORAD_CAT_ID"]))
    truncated = max(0, len(accepted) - MAX_OBJECTS)
    accepted = accepted[:MAX_OBJECTS]
    if not accepted:
        raise ValueError("No accepted orbital elements")
    canonical = json.dumps(
        accepted, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return {
        "objects": accepted,
        "generation": hashlib.sha256(canonical.encode()).hexdigest(),
        "rejected_count": rejected,
        "truncated_count": truncated,
    }


def eligible_objects(objects: list[dict], now: datetime) -> list[dict]:
    return [
        obj
        for obj in objects
        if now - timedelta(hours=72)
        <= utc_epoch(obj["EPOCH"])
        <= now + timedelta(minutes=10)
    ]
