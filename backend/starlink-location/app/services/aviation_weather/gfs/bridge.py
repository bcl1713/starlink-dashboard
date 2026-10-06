"""API-only projection; imports neither ecCodes nor NumPy nor ingest work."""

import asyncio
import hashlib
import re
import time
import uuid
from contextlib import ExitStack

from app.models.aviation_weather import WeatherProduct
from app.services.overview_weather.protocol import WeatherUnavailable
from starlette.datastructures import Headers
from starlette.responses import FileResponse, JSONResponse, Response

from .ipc import GfsMailbox
from .store import GfsProductStore, canonical, control_lock, read_json

ACK_SECONDS = 15
FILES = {"grid.json", "u.bin", "v.bin", "t.bin", "mask.bin"}


def unavailable_products(settings, now_ms):
    return [_envelope(kind, settings, now_ms) for kind in ("winds", "temperature")]


def _envelope(kind, settings, now_ms, descriptor=None, body=None):
    enabled = getattr(settings, kind)
    base = {
        "state": "unavailable" if enabled else "off",
        "layer_id": f"gfs-{kind}",
        "product_type": "winds" if kind == "winds" else "air-temperature",
        "representation": "latlon-grid-v1",
        "source_id": "noaa-ncep-gfs",
        "provenance": "NOAA NCEP GFS; dashboard regular-grid resampling and terrain masking; native pressure surface",
        "attribution": [
            {"label": "NOAA NCEP GFS", "url": "https://www.weather.gov/disclaimer/"}
        ],
        "time_kind": "forecast",
        "method_kind": "numerical-model",
        "validity_kind": "instant",
        "vertical": {
            "kind": "pressure",
            "pressure_pa": float(settings.gfs_selection.pressure_pa),
        },
        "generated_at_ms": now_ms,
        "product_id": hashlib.sha256(
            canonical(
                {
                    "source": "noaa-ncep-gfs",
                    "kind": kind,
                    "selection": settings.gfs_selection.model_dump(),
                }
            )
        ).hexdigest(),
    }
    if not enabled or descriptor is None:
        return WeatherProduct(**base)
    fresh, expiry = (
        descriptor.run_at_ms + 9 * 3600000,
        descriptor.run_at_ms + 18 * 3600000,
    )
    base.update(
        state="stale" if now_ms >= fresh else "ready",
        time_kind="analysis" if descriptor.lead_seconds == 0 else "forecast",
        product_id=descriptor.product_id,
        instance_id=descriptor.instance_id,
        vertical=descriptor.vertical,
        grid=descriptor.grid,
        run_at_ms=descriptor.run_at_ms,
        lead_seconds=descriptor.lead_seconds,
        valid_at_ms=descriptor.valid_at_ms,
        retrieved_at_ms=descriptor.retrieved_at_ms,
        fresh_until_ms=fresh,
        expires_at_ms=expiry,
        coverage={
            "generation": descriptor.instance_id,
            "expires_at_ms": expiry,
            "mask_encoding": "uint8-validity-v1",
            "missing_meaning": "unknown-not-clear",
            "feed_completeness": "unknown",
        },
        payload={
            "path": f"/api/aviation-weather/v1/products/{descriptor.instance_id}/grid.json",
            "sha256": hashlib.sha256(body).hexdigest(),
            "content_type": "application/json",
            "encoded_bytes": len(body)
            + sum(buffer.byte_length for buffer in descriptor.buffers.values()),
            "decoded_bytes": 5 * 1024**2,
            "gpu_bytes": 2 * 1024**2,
        },
    )
    return WeatherProduct(**base)


class LeasedFileResponse(FileResponse):
    def __init__(self, bridge, instance, filename, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bridge, self.instance, self.filename = bridge, instance, filename

    async def __call__(self, scope, receive, send):
        # Acquire only when ASGI starts the response. A returned-but-discarded
        # response (disconnect wins the route guard) owns no open lease.
        with ExitStack() as leases:
            try:
                with control_lock(self.bridge.mailbox.root, timeout=0):
                    leases.enter_context(
                        self.bridge.store.lease(self.instance, blocking=False)
                    )
                    admitted = self.bridge._admitted(
                        self.instance, self.filename, self.bridge.now_ms()
                    )
            except (OSError, ValueError, TimeoutError):
                admitted = False
            if not admitted:
                return await JSONResponse(
                    {"detail": "Aviation weather product unavailable"},
                    status_code=404,
                    headers={"Cache-Control": "no-store"},
                )(scope, receive, send)
            if Headers(scope=scope).get("if-none-match") == self.headers["etag"]:
                return await Response(
                    status_code=304,
                    headers={
                        "Cache-Control": "private, no-cache",
                        "ETag": self.headers["etag"],
                    },
                )(scope, receive, send)
            return await super().__call__(scope, receive, send)


class GfsBridge:
    def __init__(
        self, settings, root, mailbox, *, clock=time.time, monotonic=time.monotonic
    ):
        self.settings = settings
        self.mailbox = GfsMailbox(mailbox, settings, monotonic=monotonic)
        self.store = GfsProductStore(root, mailbox, settings, readonly=True)
        self.owner = uuid.uuid4().hex
        self.clock, self.monotonic = clock, monotonic
        self._anchor = None
        self._last_clock = 0
        self._closed = False

    def now_ms(self):
        return int(self.clock() * 1000)

    def _valid_clock(self, now_ms):
        mono = self.monotonic()
        if self._anchor is None:
            self._anchor = now_ms, mono
        expected = self._anchor[0] + (mono - self._anchor[1]) * 1000
        if now_ms < self._last_clock or expected - now_ms > 15000:
            return False
        self._last_clock = now_ms
        if now_ms > expected:
            self._anchor = now_ms, mono
        return True

    def _save(self, changes):
        with control_lock(self.mailbox.root, timeout=1):
            before = self.settings.get()
            settings = self.settings.update(changes)
            if before.revision != settings.revision:
                self.mailbox.invalidate_locked(settings.revision)
            return settings

    async def save(self, changes):
        return await asyncio.to_thread(self._save, changes)

    async def settings_changed(self, settings):
        try:
            async with asyncio.timeout(ACK_SECONDS):
                while not await asyncio.to_thread(
                    self.mailbox.acknowledged, settings.revision
                ):
                    await asyncio.sleep(0.1)
        except TimeoutError:
            raise WeatherUnavailable() from None

    def _current(self, settings, now_ms):
        if (
            self._closed
            or not self._valid_clock(now_ms)
            or not self.mailbox.healthy(now_ms)
        ):
            return ()
        pointer = read_json(self.store.root / "current.json")
        if pointer["revision"] != settings.revision:
            return ()
        return self.store.read_current(settings.gfs_selection, now_ms)

    def _products(self, settings, now_ms):
        try:
            if self._closed or not self._valid_clock(now_ms):
                self.mailbox.withdraw(self.owner)
                return unavailable_products(settings, now_ms)
            self.mailbox.renew(self.owner, settings, now_ms)
            with control_lock(self.mailbox.root, timeout=1):
                current = self._current(settings, now_ms)
                if len(current) != 2:
                    return unavailable_products(settings, now_ms)
                return [
                    _envelope(
                        kind,
                        settings,
                        now_ms,
                        descriptor,
                        (
                            self.store.root
                            / "products"
                            / descriptor.instance_id
                            / "grid.json"
                        ).read_bytes(),
                    )
                    for kind, descriptor in zip(
                        ("winds", "temperature"), current, strict=True
                    )
                ]
        except (OSError, ValueError, KeyError, TimeoutError):
            return unavailable_products(settings, now_ms)

    async def products(self, settings, now_ms):
        return await asyncio.to_thread(self._products, settings, now_ms)

    def _admitted(self, instance, filename, now_ms):
        settings = self.settings.get()
        current = self._current(settings, now_ms)
        return (
            any(
                descriptor.instance_id == instance and getattr(settings, kind)
                for kind, descriptor in zip(("winds", "temperature"), current)
            )
            and filename in FILES
        )

    def _response(self, instance, filename, settings, now_ms):
        if not re.fullmatch(r"[a-f0-9]{64}", instance) or filename not in FILES:
            return None
        try:
            with control_lock(self.mailbox.root, timeout=1), self.store.lease(
                instance, blocking=False
            ) as descriptor:
                if settings != self.settings.get() or not self._admitted(
                    instance, filename, now_ms
                ):
                    return None
                path = self.store.root / "products" / instance / filename
                expected = (
                    1024**2
                    if filename == "grid.json"
                    else descriptor.buffers[filename.removesuffix(".bin")].byte_length
                )
                if (
                    path.is_symlink()
                    or path.stat().st_size > expected
                    or (filename != "grid.json" and path.stat().st_size != expected)
                ):
                    return None
                with path.open("rb") as stream:
                    body = stream.read(expected + 1)
                if len(body) > expected:
                    return None
                digest = hashlib.sha256(body).hexdigest()
                if filename != "grid.json":
                    buffer = descriptor.buffers[filename.removesuffix(".bin")]
                    if len(body) != buffer.byte_length or digest != buffer.sha256:
                        return None
                return LeasedFileResponse(
                    self,
                    instance,
                    filename,
                    path,
                    media_type=(
                        "application/json"
                        if filename == "grid.json"
                        else "application/octet-stream"
                    ),
                    headers={
                        "Cache-Control": "private, no-cache",
                        "ETag": f'"{digest}"',
                    },
                )
        except (OSError, ValueError, KeyError, TimeoutError):
            return None

    async def response(self, instance, filename, settings, now_ms):
        return await asyncio.to_thread(
            self._response, instance, filename, settings, now_ms
        )

    async def aclose(self):
        self._closed = True
        await asyncio.to_thread(self.mailbox.withdraw, self.owner)
