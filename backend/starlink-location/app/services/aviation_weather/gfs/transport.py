"""Bounded, version-pinned acquisition from the public NOAA GFS bucket."""

import asyncio
import hashlib
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from app.models.aviation_grid import GfsSelection, RangeRef, SourceBundle, SourceRef

from .inventory import (
    MAX_METADATA,
    discover_runs,
    listing,
    listing_values,
    select_ranges,
    select_time,
)
from .quota import GfsQuota

BASE = "https://noaa-gfs-bdp-pds.s3.amazonaws.com/"
EXCHANGE_SECONDS = 30


class GfsTransport:
    def __init__(self, quota: GfsQuota, *, client=None, clock=time.time):
        self.quota = quota
        self.clock = clock
        self._owned = client is None
        self.client = client or httpx.AsyncClient(
            follow_redirects=False,
            timeout=30,
            limits=httpx.Limits(max_connections=2, max_keepalive_connections=2),
            headers={"User-Agent": "starlink-dashboard/aviation-weather-gfs"},
        )

    async def _exchange(
        self, method, key="", *, params=None, headers=None, limit=0, sink=None
    ):
        if (
            not re.fullmatch(r"[a-zA-Z0-9._/-]*", key)
            or ".." in key
            or key.startswith("/")
        ):
            raise ValueError("Invalid source object key")
        token = self.quota.reserve(limit)
        try:
            self.quota.attempt()
            async with asyncio.timeout(EXCHANGE_SECONDS):
                async with self.client.stream(
                    method,
                    BASE + key,
                    params=params,
                    headers={"Accept-Encoding": "identity", **(headers or {})},
                    follow_redirects=False,
                ) as response:
                    chunks = []
                    size = 0
                    if (
                        response.headers.get("content-encoding", "identity")
                        != "identity"
                    ):
                        raise ValueError("Encoded scientific response")
                    async for chunk in response.aiter_raw():
                        self.quota.charge(token, len(chunk))
                        size += len(chunk)
                        if size > limit:
                            raise ValueError("Scientific response exceeds limit")
                        if sink:
                            sink.write(chunk)
                        else:
                            chunks.append(chunk)
                    return (
                        response.status_code,
                        response.headers,
                        b"".join(chunks),
                        size,
                    )
        finally:
            self.quota.release(token)

    async def _metadata(self, key="", *, params=None):
        status, _, body, _ = await self._exchange(
            "GET", key, params=params, limit=MAX_METADATA
        )
        if status != 200:
            raise ValueError("Scientific metadata unavailable")
        return body

    async def _head(self, key):
        status, headers, _, _ = await self._exchange("HEAD", key)
        etag = headers.get("etag", "")
        try:
            size = int(headers.get("content-length", ""))
        except ValueError as error:
            raise ValueError("Missing source size") from error
        if (
            status != 200
            or not re.fullmatch(r'"[A-Za-z0-9-]+"', etag)
            or not 0 < size <= 1024**3
        ):
            raise ValueError("Missing strong source validator")
        return SourceRef(key, etag, size)

    async def _list(self, prefix, delimiter=None):
        params = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
        if delimiter:
            params["delimiter"] = delimiter
        body = await self._metadata(params=params)
        root = listing(body)
        if listing_values(root, "IsTruncated") != ("false",):
            raise ValueError("Scientific listing exceeds bounded inventory")
        return body, root

    async def download(self, ref: RangeRef, path: Path) -> str:
        expected = ref.end - ref.start + 1
        if not 0 <= ref.start <= ref.end < ref.source.size or expected > 32 * 1024**2:
            raise ValueError("Invalid scientific range")
        stage = path.with_suffix(path.suffix + ".partial")
        try:
            with stage.open("xb") as stream:
                status, headers, _, size = await self._exchange(
                    "GET",
                    ref.source.key,
                    headers={
                        "If-Match": ref.source.etag,
                        "Range": f"bytes={ref.start}-{ref.end}",
                    },
                    limit=expected,
                    sink=stream,
                )
                if (
                    status != 206
                    or headers.get("etag") != ref.source.etag
                    or headers.get("content-range")
                    != f"bytes {ref.start}-{ref.end}/{ref.source.size}"
                    or size != expected
                ):
                    raise ValueError("Scientific range identity mismatch")
                stream.flush()
                os.fsync(stream.fileno())
            digest = hashlib.sha256(stage.read_bytes()).hexdigest()
            stage.replace(path)
            return digest
        finally:
            stage.unlink(missing_ok=True)

    async def acquire(self, selection: GfsSelection, stage: Path) -> SourceBundle:
        now = int(self.clock() * 1000)
        today = datetime.fromtimestamp(now / 1000, timezone.utc)
        runs = set()
        for date in (today, today - timedelta(days=1)):
            body, _ = await self._list(date.strftime("gfs.%Y%m%d/"), "/")
            runs.update(discover_runs(body))
        admitted = sorted(
            (run for run in runs if now - 18 * 3600000 < run <= now), reverse=True
        )
        selected = None
        for run in admitted[:8]:
            prefix = datetime.fromtimestamp(run / 1000, timezone.utc).strftime(
                "gfs.%Y%m%d/%H/atmos/"
            )
            cycle = datetime.fromtimestamp(run / 1000, timezone.utc).strftime("%H")
            _, root = await self._list(prefix + f"gfs.t{cycle}z.pgrb2.0p25.f")
            keys = listing_values(root, "Key")
            objects = {}
            for key in keys:
                match = re.fullmatch(
                    re.escape(prefix) + r"gfs\.t\d{2}z\.pgrb2\.0p25\.f(\d{3})", key
                )
                if match and key + ".idx" in keys:
                    cycle = datetime.fromtimestamp(run / 1000, timezone.utc).strftime(
                        "%H"
                    )
                    if f"gfs.t{cycle}z." not in key:
                        raise ValueError("Source cycle mismatch")
                    objects[int(match[1]) * 3600] = key
            lead = select_time(
                run, tuple(objects), now + selection.horizon_hours * 3600000
            )
            if lead is not None:
                selected = run, lead, objects[lead]
                break
        if selected is None:
            raise ValueError("No compatible actual source object")
        run, lead, key = selected
        before = await self._head(key)
        index = await self._metadata(key + ".idx")
        if await self._head(key) != before:
            raise ValueError("Source replaced during inventory read")
        ranges = select_ranges(index, before, run, lead, (selection.pressure_pa,))
        stage.mkdir(parents=True, exist_ok=False)
        paths, hashes = [], []
        try:
            for ref in ranges:
                path = stage / f"{ref.quantity}-{ref.pressure_pa or 0}.grib2"
                hashes.append(await self.download(ref, path))
                paths.append(path)
            if await self._head(key) != before:
                raise ValueError("Source replaced during range acquisition")
            (stage / "source.idx").write_bytes(index)
            return SourceBundle(
                run, lead, ranges, tuple(paths), tuple(hashes), int(self.clock() * 1000)
            )
        except BaseException:
            for path in stage.iterdir():
                path.unlink()
            stage.rmdir()
            raise

    async def aclose(self):
        if self._owned:
            await self.client.aclose()
