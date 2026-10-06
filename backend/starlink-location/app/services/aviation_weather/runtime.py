"""Shared optional bulletin leases and bounded immutable local snapshots."""

import asyncio
import hashlib
import json
import time
from collections import OrderedDict, deque
from dataclasses import dataclass

from app.models.aviation_weather import WeatherProduct
from app.services.overview_weather.protocol import WeatherUnavailable

from .catalog import identity
from .decode import await_owned, normalize_in_worker
from .relations import cancellation_matches

LAYERS = {
    "metar": ("metar-speci", "station-v1", "observation", 300),
    "taf": ("taf", "station-v1", "forecast", 600),
    "sigmet": ("international-sigmet", "advisory-v1", "forecast", 300),
}
MAX_RETAINED = 64 * 1024**2


@dataclass(frozen=True)
class Snapshot:
    instance: str
    body: bytes
    retrieved: int
    fresh: int
    expires: int
    completeness: str
    revision: int
    decoded_bytes: int
    gpu_bytes: int


@dataclass
class Lease:
    task: asyncio.Task
    readers: int = 0


class AviationWeatherService:
    def __init__(
        self, store, transport, *, utc_ms=None, monotonic=None, normalize=None
    ):
        self.store, self.transport = store, transport
        self.utc_ms = utc_ms or (lambda: int(time.time() * 1000))
        self.monotonic = monotonic or time.monotonic
        self.normalize = normalize or normalize_in_worker
        self._settings = None
        self._tasks: dict[str, Lease] = {}
        self._retiring: set[asyncio.Task] = set()
        self._snapshots: dict[str, OrderedDict[str, Snapshot]] = {}
        self._current: dict[str, str] = {}
        self._lineage: OrderedDict[str, tuple[int, dict]] = OrderedDict()
        self._next: dict[str, float] = {}
        self._attempts = deque()
        self._http_slots = asyncio.Semaphore(2)
        self._decoder = asyncio.Semaphore(1)
        self._closed = False
        self._closing = None
        self._settings_lock = asyncio.Lock()

    @property
    def pending_count(self):
        return len(self._tasks)

    def _attempt(self):
        now = self.monotonic()
        while self._attempts and self._attempts[0] <= now - 60:
            self._attempts.popleft()
        if len(self._attempts) >= 20:
            raise WeatherUnavailable()
        self._attempts.append(now)

    async def settings_changed(self, settings):
        async with self._settings_lock:
            if (
                self._settings is not None
                and settings.revision < self._settings.revision
            ):
                return
            previous = self._settings
            self._settings = settings
            stopped = []
            for layer in LAYERS:
                if not getattr(settings, layer):
                    lease = self._tasks.pop(layer, None)
                    if lease is not None:
                        self._retiring.add(lease.task)
                        lease.task.add_done_callback(self._retiring.discard)
                        lease.task.cancel()
                        stopped.append(lease.task)
                    self._snapshots.pop(layer, None)
                    self._current.pop(layer, None)
                    self._next.pop(layer, None)
                elif previous is not None and not getattr(previous, layer):
                    self._next.pop(layer, None)
            await await_owned(
                asyncio.ensure_future(asyncio.gather(*stopped, return_exceptions=True))
            )

    def _enabled(self, layer):
        return (
            not self._closed
            and self._settings is not None
            and getattr(self._settings, layer)
        )

    def _prune(self):
        now = self.utc_ms()
        for key, (recorded, _) in list(self._lineage.items()):
            if now - recorded >= 86400000:
                del self._lineage[key]
        for layer, snapshots in list(self._snapshots.items()):
            for key, value in list(snapshots.items()):
                if now >= value.expires or now < value.retrieved - 60000:
                    del snapshots[key]
            if not snapshots:
                del self._snapshots[layer]

    def _advisory_history(self, collection, now):
        for feature in collection["features"]:
            properties = feature["properties"]
            if properties.get("cancelled") or properties.get("revision"):
                key = feature["id"]
                if key not in self._lineage:
                    self._lineage[key] = (now, dict(properties))
        while len(self._lineage) > 500:
            self._lineage.popitem(last=False)
        for feature in collection["features"]:
            p = feature["properties"]
            if p.get("cancelled"):
                continue
            for recorded, relation in self._lineage.values():
                if (
                    not relation.get("cancelled")
                    or relation.get("valid_from_ms", now + 1) > now
                    or now - recorded >= 86400000
                ):
                    continue
                # A cancellation supersedes an older overlapping bulletin, never
                # a later independent use of the same issuer/FIR/series.
                if cancellation_matches(p, relation):
                    p["cancelled"] = True
                    feature["geometry"] = None
                    break
        return collection

    async def _refresh(self, layer):
        deadline = self.monotonic() + 150
        try:
            async with asyncio.timeout(30):
                async with self._http_slots:
                    raw = await self.transport.fetch(layer, self._attempt)
            now = self.utc_ms()
            async with asyncio.timeout(max(0.001, deadline - self.monotonic())):
                async with self._decoder:
                    collection = await self.normalize(layer, raw, now)
            if not self._enabled(layer):
                raise WeatherUnavailable()
            features = collection.get("features")
            if (
                collection.get("type") != "FeatureCollection"
                or not isinstance(features, list)
                or len(features) > (500 if layer == "sigmet" else 5000)
            ):
                raise WeatherUnavailable()
            if layer == "sigmet":
                collection = self._advisory_history(collection, now)
            body = json.dumps(
                collection, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
            # Retain bounded station subsets while explicitly reporting omissions.
            # Advisories are never silently dropped to meet a byte budget.
            if layer in {"metar", "taf"} and len(body) > 1024**2:
                original = len(features)
                buckets = {}
                for feature in features:
                    lon, lat = feature["geometry"]["coordinates"]
                    cell = (int((lat + 90) // 10), int((lon + 180) // 10))
                    buckets.setdefault(cell, []).append(feature)
                ordered = [buckets[key] for key in sorted(buckets)]
                features = [
                    item
                    for rank in range(max(map(len, ordered), default=0))
                    for bucket in ordered
                    if rank < len(bucket)
                    for item in [bucket[rank]]
                ]
                low, high = 0, original
                while low < high:
                    middle = (low + high + 1) // 2
                    trial = {
                        **collection,
                        "features": features[:middle],
                        "feed_completeness": "partial",
                        "omitted_features": collection.get("omitted_features", 0)
                        + original
                        - middle,
                    }
                    encoded = json.dumps(
                        trial, sort_keys=True, separators=(",", ":"), allow_nan=False
                    ).encode()
                    if len(encoded) <= 1024**2:
                        low = middle
                    else:
                        high = middle - 1
                collection = {
                    **collection,
                    "features": features[:low],
                    "feed_completeness": "partial",
                    "omitted_features": collection.get("omitted_features", 0)
                    + original
                    - low,
                }
                features = collection["features"]
                body = json.dumps(
                    collection, sort_keys=True, separators=(",", ":"), allow_nan=False
                ).encode()
            if not body or len(body) > 1024**2:
                raise WeatherUnavailable()
            valid_expiries = [
                item["properties"]["expires_at_ms"]
                for item in features
                if item["properties"]["expires_at_ms"] > now
            ]
            expires = (
                max(valid_expiries)
                if valid_expiries
                else now + 2 * LAYERS[layer][3] * 1000
            )
            if layer == "metar":
                expires = min(expires, now + 7200000)
            elif layer == "sigmet":
                # Retained geometry must not outlive a known future cancellation,
                # even if the refresh at that transition fails.
                transitions = [
                    relation["valid_from_ms"]
                    for _, relation in self._lineage.values()
                    if relation.get("cancelled")
                    and relation["valid_from_ms"] > now
                    and any(
                        not item["properties"].get("cancelled")
                        and cancellation_matches(item["properties"], relation)
                        for item in features
                    )
                ]
                if transitions:
                    expires = min(expires, min(transitions))
            fresh = min(expires, now + 2 * LAYERS[layer][3] * 1000)
            if layer == "metar" and features:
                fresh = min(
                    fresh,
                    max(item["properties"]["fresh_until_ms"] for item in features),
                )
            instance = hashlib.sha256(body).hexdigest()
            candidate = Snapshot(
                instance,
                body,
                now,
                fresh,
                expires,
                collection["feed_completeness"],
                self._settings.revision,
                len(body) * 4 + (3_600_000 if layer == "sigmet" else 0),
                (
                    1_200_000
                    if layer == "sigmet"
                    else len(features) * (192 if layer == "taf" else 24)
                ),
            )
            self._prune()
            snapshots = self._snapshots.setdefault(layer, OrderedDict())
            snapshots[instance] = candidate
            self._current[layer] = instance
            snapshots.move_to_end(instance)
            while len(snapshots) > 2:
                snapshots.popitem(last=False)
            while (
                sum(
                    len(value.body)
                    for values in self._snapshots.values()
                    for value in values.values()
                )
                > MAX_RETAINED
            ):
                previous = next(
                    (
                        (key, values)
                        for key, values in self._snapshots.items()
                        if len(values) > 1
                    ),
                    None,
                )
                if previous is None:
                    del snapshots[instance]
                    raise WeatherUnavailable()
                previous[1].popitem(last=False)
            self._next[layer] = self.monotonic() + LAYERS[layer][3]
        except asyncio.CancelledError:
            raise
        except (
            WeatherUnavailable,
            TimeoutError,
            ValueError,
            TypeError,
            KeyError,
            OSError,
        ) as error:
            self._next[layer] = self.monotonic() + (
                error.retry_after_seconds
                if isinstance(error, WeatherUnavailable)
                else 30
            )

    async def _acquire(self, layer):
        if not self._enabled(layer) or self.monotonic() < self._next.get(layer, -1):
            return
        lease = self._tasks.get(layer)
        if lease is None:
            lease = Lease(asyncio.create_task(self._refresh(layer)))
            self._tasks[layer] = lease
        lease.readers += 1
        try:
            await asyncio.shield(lease.task)
        except asyncio.CancelledError:
            if asyncio.current_task().cancelling():
                raise
        finally:
            lease.readers -= 1
            if lease.readers == 0:
                if self._tasks.get(layer) is lease:
                    del self._tasks[layer]
                self._retiring.add(lease.task)
                lease.task.add_done_callback(self._retiring.discard)
                if not lease.task.done():
                    lease.task.cancel()
                await await_owned(
                    asyncio.ensure_future(
                        asyncio.gather(lease.task, return_exceptions=True)
                    )
                )

    def _product(self, layer, now):
        product_type, representation, time_kind, _ = LAYERS[layer]
        capability = identity(
            {
                "schema": "aviation-weather-v1",
                "source_id": "awc",
                "product_type": product_type,
                "representation": representation,
                "normalization_version": "awc-bulletins-v1",
                "units": "SI",
                "coverage": "feature-collection-v1",
            }
        )
        base = {
            "layer_id": layer,
            "product_type": product_type,
            "representation": representation,
            "source_id": "awc",
            "provenance": "AWC dissemination; originating station/issuer retained per feature",
            "attribution": [
                {
                    "label": "NOAA Aviation Weather Center / originating issuers",
                    "url": "https://aviationweather.gov/",
                }
            ],
            "time_kind": time_kind,
            "method_kind": "reported",
            "validity_kind": "collection",
            "vertical": {
                "kind": "surface" if layer in {"metar", "taf"} else "not-applicable"
            },
            "generated_at_ms": now,
            "product_id": capability,
        }
        if not self._enabled(layer):
            return WeatherProduct(state="off", **base)
        snapshots = self._snapshots.get(layer)
        if not snapshots:
            return WeatherProduct(state="unavailable", **base)
        snapshot = snapshots.get(self._current.get(layer))
        if snapshot is None:
            return WeatherProduct(state="unavailable", **base)
        return WeatherProduct(
            **base,
            state="stale" if now >= snapshot.fresh else "ready",
            instance_id=snapshot.instance,
            retrieved_at_ms=snapshot.retrieved,
            fresh_until_ms=snapshot.fresh,
            expires_at_ms=snapshot.expires,
            coverage={
                "generation": snapshot.instance,
                "expires_at_ms": snapshot.expires,
                "mask_encoding": "feature-collection-v1",
                "missing_meaning": "unknown-not-clear",
                "feed_completeness": snapshot.completeness,
            },
            payload={
                "path": f"/api/aviation-weather/v1/products/{snapshot.instance}/{layer}.json",
                "sha256": snapshot.instance,
                "content_type": "application/geo+json",
                "encoded_bytes": len(snapshot.body),
                "decoded_bytes": snapshot.decoded_bytes,
                "gpu_bytes": snapshot.gpu_bytes,
            },
        )

    def admitted_products(self, now):
        self._prune()
        return [self._product(layer, now) for layer in LAYERS]

    async def products(self):
        await self.settings_changed(self.store.get())
        if self._closed:
            raise WeatherUnavailable()
        await asyncio.gather(*(self._acquire(layer) for layer in LAYERS))
        self._prune()
        now = self.utc_ms()
        return self.admitted_products(now)

    def payload(self, instance, filename):
        self._prune()
        layer = filename.removesuffix(".json")
        if (
            filename != f"{layer}.json"
            or layer not in LAYERS
            or not self._enabled(layer)
        ):
            return None
        if self._current.get(layer) != instance:
            return None
        snapshot = self._snapshots.get(layer, {}).get(instance)
        return snapshot.body if snapshot is not None else None

    async def _close(self):
        self._closed = True
        tasks = list({*(lease.task for lease in self._tasks.values()), *self._retiring})
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
        self._snapshots.clear()
        self._current.clear()
        self._lineage.clear()
        await self.transport.aclose()

    async def aclose(self):
        if self._closing is None:
            self._closing = asyncio.create_task(self._close())
        await await_owned(self._closing)
