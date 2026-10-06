"""adsb.lol adapter: convert readsb position observation time, never message age."""

import math
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from email.utils import parsedate_to_datetime

import httpx

from app.models.overview_adsb import AdsbAltitude, AdsbContact


def _number(value: object) -> float | None:
    if type(value) not in (int, float):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    return number if math.isfinite(number) else None


def _text(value: object) -> str | None:
    return value.strip() or None if isinstance(value, str) else None


def normalize_contact(
    record: dict[str, object],
    response_now_ms: float,
    acquired_at_ms: float,
    from_military_feed: bool,
) -> AdsbContact | None:
    hex_code = _text(record.get("hex"))
    if hex_code is None or re.fullmatch(r"[0-9a-fA-F]{6}", hex_code) is None:
        return None
    now = _number(response_now_ms)
    acquired = _number(acquired_at_ms)
    if now is None or acquired is None or now <= 0 or acquired <= 0:
        return None
    position = None
    for candidate in (record, record.get("lastPosition")):
        if not isinstance(candidate, dict):
            continue
        lat = _number(candidate.get("lat"))
        lon = _number(candidate.get("lon"))
        age = _number(candidate.get("seen_pos"))
        if lat is None or lon is None or age is None:
            continue
        observed = now - age * 1000
        if (
            -90 <= lat <= 90
            and -180 <= lon <= 180
            and age >= 0
            and 0 <= observed <= acquired
        ):
            position = (lat, lon, observed)
            break
    if position is None:
        return None
    altitude = None
    for field, source in (("alt_baro", "barometric"), ("alt_geom", "geometric")):
        value = _number(record.get(field))
        if value is not None:
            altitude = AdsbAltitude(value=value, source=source)
            break
    speed = _number(record.get("gs"))
    track = _number(record.get("track"))
    flags = record.get("dbFlags")
    military = (
        True
        if from_military_feed
        else (bool(flags & 1) if type(flags) is int and flags >= 0 else None)
    )
    return AdsbContact(
        hex=hex_code.upper(),
        callsign=_text(record.get("flight")),
        registration=_text(record.get("r")),
        aircraft_type=_text(record.get("t")),
        military=military,
        latitude=position[0],
        longitude=position[1],
        position_observed_at_ms=position[2],
        acquired_at_ms=acquired,
        altitude=altitude,
        ground_speed_knots=speed if speed is not None and speed >= 0 else None,
        track_degrees=track if track is not None and 0 <= track < 360 else None,
    )


@dataclass(frozen=True)
class AdsbProviderResult:
    contacts: list[AdsbContact]
    acquired_at_ms: float


class AdsbProviderError(Exception):
    def __init__(self, message: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class AdsbLolProvider:
    # readsb's documented find_hex limit; larger acquisitions are chunked.
    HEX_BATCH_LIMIT = 1000

    def __init__(
        self, client: httpx.AsyncClient, time_source: Callable[[], float] = time.time
    ) -> None:
        self._client = client
        self._time = time_source

    async def fetch_military(self) -> AdsbProviderResult:
        return await self._fetch("/v2/mil", True)

    async def fetch_hex(self, hex_code: str) -> AdsbProviderResult:
        return await self.fetch_hexes([hex_code])

    async def fetch_hexes(self, hex_codes: list[str]) -> AdsbProviderResult:
        if any(re.fullmatch(r"[0-9A-F]{6}", code) is None for code in hex_codes):
            raise AdsbProviderError("Invalid ICAO hex")
        codes = list(dict.fromkeys(hex_codes))
        if len(codes) > self.HEX_BATCH_LIMIT:
            raise AdsbProviderError("ICAO hex batch exceeds provider limit")
        if not codes:
            return AdsbProviderResult([], self._time() * 1000)
        # httpx preserves these escapes; a raw comma would remain unencoded.
        return await self._fetch("/v2/hex/" + "%2C".join(codes), False)

    async def _fetch(self, path: str, military: bool) -> AdsbProviderResult:
        try:
            response = await self._client.get(path)
        except httpx.HTTPError as error:
            raise AdsbProviderError("Provider transport failed") from error
        acquired = self._time() * 1000
        if not response.is_success:
            retry = response.headers.get("Retry-After")
            seconds = None
            if retry:
                try:
                    seconds = float(retry)
                except ValueError:
                    try:
                        seconds = (
                            parsedate_to_datetime(retry).timestamp() - acquired / 1000
                        )
                    except (ValueError, TypeError, OverflowError):
                        pass
                if seconds is not None:
                    seconds = max(0, seconds) if math.isfinite(seconds) else None
            raise AdsbProviderError(f"Provider HTTP {response.status_code}", seconds)
        try:
            payload = response.json()
        except ValueError as error:
            raise AdsbProviderError("Provider returned invalid JSON") from error
        if not isinstance(payload, dict) or not isinstance(payload.get("ac"), list):
            raise AdsbProviderError("Provider returned invalid aircraft envelope")
        now = _number(payload.get("now"))
        if now is None or now <= 0 or payload.get("msg") not in (None, "", "No error"):
            raise AdsbProviderError(
                "Provider returned invalid timestamp or failure status"
            )
        contacts = []
        for record in payload["ac"]:
            if isinstance(record, dict):
                contact = normalize_contact(record, now, acquired, military)
                if contact is not None:
                    contacts.append(contact)
        return AdsbProviderResult(contacts, acquired)
