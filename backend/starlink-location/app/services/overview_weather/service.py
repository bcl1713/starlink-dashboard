"""Admit eligible observed frames and expose only reconstructed same-origin tiles."""

import asyncio
import json
import re
import struct

from app.models.overview_weather import WeatherManifest, WeatherSettings

from .acquisitions import WeatherAcquisitionPool
from .clock import WeatherClock
from .protocol import WeatherPayload, WeatherUnavailable
from .settings import WeatherSettingsStore

METADATA_URL = "https://api.rainviewer.com/public/weather-maps.json"
TILE_HOST = "https://tilecache.rainviewer.com"
DAY_MS = 86400000


class WeatherTileError(Exception):
    def __init__(self, status_code: int):
        super().__init__("Weather tile unavailable")
        self.status_code = status_code


def validate_png(body: bytes) -> None:
    if (
        len(body) < 33
        or body[:8] != b"\x89PNG\r\n\x1a\n"
        or body[8:16] != b"\x00\x00\x00\x0dIHDR"
        or struct.unpack(">II", body[16:24]) != (512, 512)
    ):
        raise ValueError("Invalid weather image")


def observed_frames(body: bytes) -> list[int]:
    payload = json.loads(body)
    if (
        not isinstance(payload, dict)
        or len(payload) > 16
        or payload.get("host") != TILE_HOST
    ):
        raise ValueError("Invalid weather metadata")
    radar = payload.get("radar")
    if not isinstance(radar, dict) or len(radar) > 8:
        raise ValueError("Invalid radar metadata")
    past = radar.get("past")
    if not isinstance(past, list) or len(past) > 32:
        raise ValueError("Invalid observed frame list")
    frames = []
    for entry in past:
        if not isinstance(entry, dict) or len(entry) > 4:
            raise ValueError("Invalid observed frame")
        timestamp, path = entry.get("time"), entry.get("path")
        if (
            type(timestamp) is not int
            or timestamp < 0
            or not isinstance(path, str)
            or not re.fullmatch(r"/v2/radar/[0-9]+", path)
            or path != f"/v2/radar/{timestamp}"
        ):
            raise ValueError("Invalid observed frame identity")
        frames.append(timestamp)
    return frames


class WeatherService:
    def __init__(
        self,
        store: WeatherSettingsStore,
        pool: WeatherAcquisitionPool,
        clock: WeatherClock,
    ):
        self.store, self.pool, self.clock = store, pool, clock
        self._revision = -1
        self._enabled = False
        self._closed = False
        self._frames: list[int] = []
        self._coverage: int | None = None
        self._settings_lock = asyncio.Lock()

    async def settings_changed(self, settings: WeatherSettings) -> None:
        async with self._settings_lock:
            if settings.revision < self._revision or (
                settings.revision == self._revision
                and settings.enabled == self._enabled
            ):
                return
            self._revision, self._enabled = settings.revision, settings.enabled
            self._frames.clear()
            self._coverage = None
            await self.pool.invalidate()

    async def _settings(self) -> WeatherSettings:
        if self._closed:
            raise WeatherUnavailable()
        try:
            settings = self.store.get()
        except (OSError, ValueError, TypeError):
            self._enabled = False
            self._frames.clear()
            self._coverage = None
            await self.pool.invalidate()
            raise WeatherUnavailable() from None
        await self.settings_changed(settings)
        return WeatherSettings(enabled=self._enabled, revision=self._revision)

    def _eligible(self, frame: int) -> bool:
        age = self.clock.utc_ms() - frame * 1000
        return -60000 <= age < 3600000

    async def _prune(self):
        self._frames = [frame for frame in self._frames if self._eligible(frame)]
        if self._coverage != self.clock.utc_ms() // DAY_MS:
            self._coverage = None
        frames, coverage = set(self._frames), self._coverage
        await self.pool.prune(
            lambda key: key[0] == "metadata"
            or (key[0] == "radar" and key[1] in frames)
            or (key[0] == "coverage" and key[1] == coverage)
        )

    def _manifest(self, state: str, revision: int, frame: int | None = None):
        now = self.clock.utc_ms()
        if state != "ready":
            return WeatherManifest(
                state=state, settings_revision=revision, generated_at_ms=now
            )
        day = now // DAY_MS
        return WeatherManifest(
            state="ready",
            settings_revision=revision,
            generated_at_ms=now,
            frame_time_ms=frame * 1000,
            coverage_token=day,
            coverage_expires_at_ms=(day + 1) * DAY_MS,
            radar_tile_template=f"/api/overview-weather/radar/{frame}/{{z}}/{{x}}/{{y}}.png",
            coverage_tile_template=f"/api/overview-weather/coverage/{day}/{{z}}/{{x}}/{{y}}.png",
        )

    def _validate_metadata(self, body: bytes) -> None:
        if not any(self._eligible(frame) for frame in observed_frames(body)):
            raise ValueError("No eligible observed weather frame")

    async def read_frame(self) -> WeatherManifest:
        settings = await self._settings()
        if not settings.enabled:
            return self._manifest("off", settings.revision)
        revision = settings.revision
        await self._prune()
        try:
            if not self._enabled or revision != self._revision:
                raise WeatherUnavailable()
            metadata = await self.pool.acquire(
                ("metadata", 0, 0, 0, 0),
                METADATA_URL,
                131072,
                "application/json",
                300,
                self._validate_metadata,
            )
            if not self._enabled or revision != self._revision:
                raise WeatherUnavailable()
            eligible = [
                frame
                for frame in observed_frames(metadata.body)
                if self._eligible(frame)
            ]
            if not eligible:
                raise WeatherUnavailable()
            selected = max(eligible + self._frames)
            self._frames = sorted(set(self._frames + [selected]), reverse=True)[:2]
            self._coverage = self.clock.utc_ms() // DAY_MS
            await self._prune()
            if not self._enabled or revision != self._revision:
                raise WeatherUnavailable()
            return self._manifest("ready", revision, selected)
        except WeatherUnavailable:
            return self._manifest(
                "unavailable" if self._enabled else "off", max(0, self._revision)
            )

    @staticmethod
    def _coordinates(z, x, y):
        if z != 2 or not 0 <= x <= 3 or not 0 <= y <= 3:
            raise WeatherTileError(400)

    async def _tile(
        self, kind: str, token: int, z: int, x: int, y: int
    ) -> WeatherPayload:
        self._coordinates(z, x, y)
        settings = await self._settings()
        if not settings.enabled:
            raise WeatherTileError(409)
        await self._prune()
        if not self._enabled:
            raise WeatherTileError(409)
        if (kind == "radar" and token not in self._frames) or (
            kind == "coverage" and token != self._coverage
        ):
            raise WeatherTileError(404)
        revision = self._revision
        path = (
            f"/v2/radar/{token}/512/2/{x}/{y}/2/1_1.png"
            if kind == "radar"
            else f"/v2/coverage/0/512/2/{x}/{y}/0/0_0.png"
        )
        ttl = (
            3600
            if kind == "radar"
            else max(0, ((token + 1) * DAY_MS - self.clock.utc_ms()) / 1000)
        )
        payload = await self.pool.acquire(
            (kind, token, z, x, y),
            TILE_HOST + path,
            2097152,
            "image/png",
            ttl,
            validate_png,
        )
        if not self._enabled or revision != self._revision:
            raise WeatherTileError(409)
        if (kind == "radar" and not self._eligible(token)) or (
            kind == "coverage" and token != self.clock.utc_ms() // DAY_MS
        ):
            await self._prune()
            raise WeatherTileError(404)
        return payload

    async def radar_tile(self, frame: int, z: int, x: int, y: int) -> WeatherPayload:
        return await self._tile("radar", frame, z, x, y)

    async def coverage_tile(
        self, coverage: int, z: int, x: int, y: int
    ) -> WeatherPayload:
        return await self._tile("coverage", coverage, z, x, y)

    async def aclose(self) -> None:
        self._closed = True
        self._enabled = False
        await self.pool.aclose()
