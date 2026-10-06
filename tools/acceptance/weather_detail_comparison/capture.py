"""Bounded, proxy-aware acquisition for a few immutable radar snapshots."""

import argparse
import gzip
import json
import re
import threading
import time
import xml.etree.ElementTree as ET
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit

from .exchange import open_exchange
from .model import CaptureSet, Snapshot, digest, relative, write_capture
from .storage import discard, publish, write_chunk

MIB = 1024**2
HOSTS = {
    "api.rainviewer.com",
    "tilecache.rainviewer.com",
    "mrms.ncep.noaa.gov",
    "s3.waw3-1.cloudferro.com",
    "api.meteogate.eu",
}
MRMS = "https://mrms.ncep.noaa.gov/2D/PrecipRate/"
OPERA = "https://s3.waw3-1.cloudferro.com/openradar-24h/"
RAINVIEWER = "https://api.rainviewer.com/public/weather-maps.json"


class RateLimited(RuntimeError):
    pass


def approved(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in HOSTS
        or parsed.port not in (None, 443)
        or parsed.username
        or parsed.password
    ):
        raise ValueError("unapproved HTTPS origin")
    return url


class Downloader:
    active_limit = 2

    def __init__(
        self,
        root,
        *,
        opener=None,
        clock=time.monotonic,
        sleep=time.sleep,
        object_limit=256 * MIB,
        storage_limit=1024 * MIB,
    ):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.opener = opener or (
            lambda url, timeout: open_exchange(url, timeout=timeout, record=self.event)
        )
        self.clock, self.sleep = clock, sleep
        self.object_limit, self.storage_limit = object_limit, storage_limit
        self.attempts = deque()
        self.lock, self.active = threading.Lock(), threading.Semaphore(2)
        self.events = self.root / "downloads.jsonl"
        if self.events.exists():
            for line in self.events.read_text().splitlines():
                event = json.loads(line)
                if (
                    event.get("event") == "attempt"
                    and self.clock() - event["monotonic"] < 60
                ):
                    self.attempts.append(event["monotonic"])

    def event(self, **values):
        with self.events.open("ab") as output:
            write_chunk(
                self.root,
                output,
                (json.dumps({"utc": time.time(), **values}) + "\n").encode(),
                self.storage_limit,
            )

    def get(self, url, filename, *, limit=None):
        approved(url)
        target = self.root / filename
        relative(self.root, target)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            return target
        temporary = target.with_suffix(target.suffix + ".partial")
        maximum = min(limit or self.object_limit, self.object_limit)
        with self.active:
            for attempt in range(2):
                with self.lock:
                    now = self.clock()
                    while self.attempts and now - self.attempts[0] >= 60:
                        self.attempts.popleft()
                    if len(self.attempts) >= 30:
                        raise RateLimited(
                            "30 attempts per rolling minute; resume later"
                        )
                    self.attempts.append(now)
                    self.event(event="attempt", monotonic=now, url=url)
                started = self.clock()
                try:
                    with self.opener(url, timeout=45) as response, temporary.open(
                        "wb"
                    ) as output:
                        size = 0
                        while True:
                            if self.clock() - started >= 45:
                                raise TimeoutError("capture deadline")
                            chunk = response.read(64 * 1024)
                            if self.clock() - started >= 45:
                                raise TimeoutError("capture deadline")
                            if not chunk:
                                break
                            size += len(chunk)
                            if size > maximum:
                                raise ValueError("download storage limit")
                            write_chunk(self.root, output, chunk, self.storage_limit)
                    publish(temporary, target, self.root)
                    self.event(
                        event="complete",
                        url=url,
                        bytes=size,
                        seconds=self.clock() - started,
                        sha256=digest(target),
                    )
                    return target
                except HTTPError as error:
                    self.event(event="failed", url=url, status=error.code)
                    if attempt or error.code not in (429, 500, 502, 503, 504):
                        raise
                    try:
                        delay = float(error.headers.get("Retry-After", "1"))
                    except ValueError:
                        raise RateLimited("invalid Retry-After") from error
                    if not 0 <= delay <= 30:
                        raise RateLimited(
                            "Retry-After exceeds bounded capture wait"
                        ) from error
                    self.sleep(delay)
                finally:
                    discard(temporary, self.root)
        raise RuntimeError("capture attempts exhausted")


def decompress(
    source: Path,
    destination: Path,
    limit=256 * MIB,
    *,
    storage_limit=1024 * MIB,
    storage_root=None,
):
    temporary = destination.with_suffix(destination.suffix + ".partial")
    try:
        with gzip.open(source, "rb") as stream, temporary.open("wb") as output:
            total = 0
            while chunk := stream.read(64 * 1024):
                total += len(chunk)
                if total > limit:
                    raise ValueError("decompression limit")
                write_chunk(
                    storage_root or destination.parent, output, chunk, storage_limit
                )
        publish(temporary, destination, storage_root or destination.parent)
    finally:
        discard(temporary, storage_root or destination.parent)
    return destination


def utc(value, pattern):
    return int(
        datetime.strptime(value, pattern).replace(tzinfo=timezone.utc).timestamp()
    )


def mrms_objects(html):
    names = set(re.findall(r"MRMS_PrecipRate_00\.00_(\d{8}-\d{6})\.grib2\.gz", html))
    return sorted(
        (utc(name, "%Y%m%d-%H%M%S"), f"MRMS_PrecipRate_00.00_{name}.grib2.gz")
        for name in names
    )


def opera_objects(xml):
    objects = []
    for entry in ET.fromstring(xml).iter():
        if entry.tag.rsplit("}", 1)[-1] == "Key" and entry.text:
            match = re.fullmatch(
                r"\d{4}/\d{2}/\d{2}/OPERA/COMP/OPERA@(\d{8}T\d{4})@0@RATE\.h5",
                entry.text,
            )
            if match:
                objects.append((utc(match[1], "%Y%m%dT%H%M"), entry.text))
    return sorted(objects)


def rainviewer_frame(metadata):
    if metadata.get("host") != "https://tilecache.rainviewer.com":
        raise ValueError("unexpected radar host")
    frames = metadata.get("radar", {}).get("past", [])
    if not frames:
        raise ValueError("no observed frame")
    for frame in frames:
        if (
            type(frame.get("time")) is not int
            or not 0 < frame["time"] <= time.time()
            or not re.fullmatch(
                r"/v2/radar/[A-Za-z0-9_-]{1,128}", frame.get("path", "")
            )
        ):
            raise ValueError("invalid observed frame")
    return max(frames, key=lambda f: f["time"])


def capture(destination: Path, max_snapshots: int = 2) -> CaptureSet:
    if max_snapshots not in (1, 2):
        raise ValueError("one or two snapshots only")
    destination = destination.resolve()
    downloader = Downloader(destination)
    snapshots, metadata = [], {"errors": [], "mode": "actual capture", "regions": {}}
    observed = int(time.time()) // 600 * 600
    try:
        path = downloader.get(RAINVIEWER, "rainviewer-metadata.json", limit=2 * MIB)
        data = json.loads(path.read_text())
        frame = rainviewer_frame(data)
        observed = frame["time"]
        metadata["rainviewer_frame"] = frame
        snapshots.append(
            Snapshot(
                "rainviewer",
                "radar",
                observed,
                int(time.time()),
                "provider RGBA",
                "EPSG:3857",
                RAINVIEWER,
                "RainViewer API terms",
                "RainViewer",
                path,
                digest(path),
            )
        )
    except (ValueError, OSError, RuntimeError) as error:
        metadata["errors"].append({"source": "rainviewer", "error": str(error)})
    for source in ("mrms", "opera"):
        try:
            if source == "mrms":
                index = downloader.get(MRMS, "mrms-index.html", limit=2 * MIB)
                candidates = mrms_objects(index.read_text())
                base, product, license_name, attribution = (
                    MRMS,
                    "PrecipRate",
                    "NOAA public data",
                    "NOAA/NSSL MRMS",
                )
            else:
                prefix = datetime.fromtimestamp(observed, timezone.utc).strftime(
                    "%Y/%m/%d/OPERA/COMP/"
                )
                index = downloader.get(
                    OPERA + "?list-type=2&max-keys=1000&prefix=" + quote(prefix),
                    "opera-index.xml",
                    limit=2 * MIB,
                )
                candidates = opera_objects(index.read_text())
                base, product, license_name, attribution = (
                    OPERA,
                    "RATE",
                    "CC BY 4.0",
                    "EUMETNET OPERA",
                )
            if not candidates:
                raise ValueError("no instantaneous rain-rate products")
            stamp, name = min(candidates, key=lambda item: abs(item[0] - observed))
            path = downloader.get(base + quote(name, safe="/@"), Path(name).name)
            if source == "mrms":
                path = decompress(path, path.with_suffix(""))
            snapshots.append(
                Snapshot(
                    source,
                    product,
                    stamp,
                    int(time.time()),
                    "mm/h",
                    "validate from source raster metadata",
                    base + quote(name, safe="/@"),
                    license_name,
                    attribution,
                    path,
                    digest(path),
                )
            )
            metadata[f"{source}_time_delta_seconds"] = stamp - observed
        except (ValueError, OSError, RuntimeError) as error:
            metadata["errors"].append({"source": source, "error": str(error)})
    result = CaptureSet(destination, tuple(snapshots), {}, metadata)
    write_capture(result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    result = capture(args.destination)
    print(
        json.dumps(
            {
                "snapshots": [s.identity for s in result.snapshots],
                "errors": result.metadata["errors"],
            }
        )
    )
