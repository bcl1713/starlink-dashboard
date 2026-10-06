"""Atomic, pinned real-source acquisitions and immutable offline replay."""

import argparse
import hashlib
import fcntl
import json
import os
import shutil
import signal
import tempfile
import time
from pathlib import Path
from .exchange import MAX_BYTES, open_exchange
from .exchange import ExchangeBudget as ExchangeBudget
from .model import object_path as object_path
from .model import (
    CapturedObject,
    CaptureManifest,
    capture_manifest_path,
    load_capture,
    write_manifest,
)

GFS_CYCLE = "2026100600"
GOES_KEY = "ABI-L2-CMIPF/2026/279/00/OR_ABI-L2-CMIPF-M6C13_G19_s20262790000209_e20262790009528_c20262790009599.nc"


class DiskReservation:
    """Reserve raw bytes atomically across acquisitions in one evidence root."""

    def __init__(self, root: Path, size: int):
        self.root = Path(root)
        self.size = size
        self.token = f"{os.getpid()}-{time.monotonic_ns()}"

    def update(self, add):
        with (self.root / ".raw-quota.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            path = self.root / ".raw-reservations.json"
            state = json.loads(path.read_text()) if path.exists() else {}
            for key, reservation in list(state.items()):
                try:
                    os.kill(reservation["pid"], 0)
                except ProcessLookupError:
                    del state[key]
            if add:
                used = sum(
                    p.stat().st_size for p in self.root.rglob("*") if p.is_file()
                )
                reserved = sum(entry["size"] for entry in state.values())
                if used + reserved + self.size > 1024**3:
                    raise ValueError("1 GiB staging quota exceeded")
                if (
                    shutil.disk_usage(self.root).free
                    < 512 * 1024 * 1024 + reserved + self.size
                ):
                    raise ValueError("insufficient disk reserve")
                state[self.token] = {"pid": os.getpid(), "size": self.size}
            else:
                state.pop(self.token, None)
            temporary = path.with_suffix(".partial")
            temporary.write_text(json.dumps(state))
            temporary.replace(path)

    def __enter__(self):
        self.update(True)
        return self

    def __exit__(self, *args):
        self.update(False)


def download(
    url,
    path,
    *,
    byte_range=None,
    command=None,
    timeout=30,
    record=lambda **x: None,
    budget=None,
):
    path = Path(path)
    if path.exists():
        raise ValueError("capture object already exists")
    partial = path.with_name(path.name + ".partial")
    size = 0
    digest = hashlib.sha256()
    try:
        with (
            open_exchange(
                url,
                byte_range=byte_range,
                command=command,
                timeout=timeout,
                record=record,
                budget=budget,
            ) as response,
            partial.open("xb") as output,
        ):
            while chunk := response.read(65536):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValueError("object exceeds 32 MiB")
                if response.length is not None and size > response.length:
                    raise ValueError("response length mismatch")
                output.write(chunk)
                digest.update(chunk)
            if not size or (response.length is not None and size != response.length):
                raise ValueError("response length mismatch")
            output.flush()
            os.fsync(output.fileno())
        partial.replace(path)
        return CapturedObject(url, byte_range, path.name, digest.hexdigest(), size)
    finally:
        partial.unlink(missing_ok=True)


def gfs_ranges(index):
    records = []
    for line in index.splitlines():
        fields = line.split(":")
        if len(fields) < 7:
            raise ValueError("invalid GFS inventory")
        records.append((int(fields[1]), fields[2:]))
    if any(a[0] >= b[0] for a, b in zip(records, records[1:])):
        raise ValueError("unordered GFS inventory")
    selected = {}
    for (start, fields), (next_start, _) in zip(records, records[1:]):
        if fields[1] in ("TMP", "UGRD", "VGRD") and fields[2] == "500 mb":
            if (
                fields[0] != "d=2026100600"
                or fields[3] != "6 hour fcst"
                or fields[1] in selected
            ):
                raise ValueError("wrong GFS identity")
            selected[fields[1]] = (start, next_start - 1)
    if set(selected) != {"TMP", "UGRD", "VGRD"}:
        raise ValueError("missing GFS 500 hPa fields")
    return selected


def capture(
    source: str,
    destination: Path,
    *,
    cycle: str | None = None,
    object_key: str | None = None,
) -> CaptureManifest:
    if source not in ("gfs", "isigmet", "goes19-c13"):
        raise ValueError("unknown source")
    if cycle not in (None, GFS_CYCLE) or (cycle is not None and source != "gfs"):
        raise ValueError("unverified cycle")
    if object_key not in (None, GOES_KEY) or (
        object_key is not None and source != "goes19-c13"
    ):
        raise ValueError("unverified object key")
    try:
        destination = Path(destination)
    except TypeError as error:
        raise ValueError("invalid capture destination") from error
    if destination.exists():
        raise ValueError("destination already exists; never replace a manifest")
    destination.parent.mkdir(parents=True, exist_ok=True)
    ownership = destination.parent / (destination.name + "-ownership.jsonl")

    def record(**event):
        with ownership.open("a") as stream:
            stream.write(
                json.dumps({"utc_ms": int(time.time() * 1000), **event}) + "\n"
            )

    record(
        event="capture_intent",
        destination=str(destination),
        staging_template=str(destination.parent / ("." + destination.name + "-*")),
        owner_pid=os.getpid(),
        owner_group=os.getpgrp(),
    )
    handlers = {}
    stage = None

    def interrupted(number, frame):
        raise InterruptedError(number)

    for sig in (signal.SIGINT, signal.SIGTERM):
        handlers[sig] = signal.signal(sig, interrupted)
    try:
        with DiskReservation(
            destination.parent, (4 if source == "gfs" else 1) * MAX_BYTES
        ):
            try:
                stage = Path(
                    tempfile.mkdtemp(
                        prefix="." + destination.name + "-", dir=destination.parent
                    )
                )
                record(event="staging_owner", path=str(stage))
                objects = []
                if source == "gfs":
                    url = "https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.20261006/00/atmos/gfs.t00z.pgrb2.0p25.f006"
                    objects.append(
                        download(url + ".idx", stage / "gfs.f006.idx", record=record)
                    )
                    for field, bounds in gfs_ranges(
                        (stage / "gfs.f006.idx").read_text()
                    ).items():
                        objects.append(
                            download(
                                url,
                                stage / (field.lower() + "-500.grib2"),
                                byte_range=bounds,
                                record=record,
                            )
                        )
                    attribution = (
                        "NOAA NCEP GFS; public NOAA dissemination; https://www.weather.gov/disclaimer/",
                    )
                elif source == "isigmet":
                    objects.append(
                        download(
                            "https://aviationweather.gov/api/data/isigmet?format=geojson",
                            stage / "isigmet.geojson",
                            record=record,
                        )
                    )
                    data = json.loads((stage / "isigmet.geojson").read_text())
                    if data.get("type") != "FeatureCollection" or not isinstance(
                        data.get("features"), list
                    ):
                        raise ValueError("invalid international SIGMET collection")
                    attribution = (
                        "NOAA Aviation Weather Center; retain originating international issuers; completeness and redistribution restrictions unresolved; https://www.weather.gov/disclaimer/",
                    )
                else:
                    objects.append(
                        download(
                            "https://noaa-goes19.s3.amazonaws.com/" + GOES_KEY,
                            stage / "goes19-c13.nc",
                            record=record,
                        )
                    )
                    attribution = (
                        "NOAA NESDIS GOES-19 ABI channel 13; https://registry.opendata.aws/noaa-goes/; processing modifications must be declared",
                    )
                manifest = CaptureManifest(
                    source, int(time.time() * 1000), tuple(objects), attribution
                )
                write_manifest(manifest, stage / "capture.json")
                stage.rename(destination)
                record(
                    event="capture_published",
                    manifest=str(destination / "capture.json"),
                )
                return load_capture(destination / "capture.json")
            finally:
                if stage is not None:
                    shutil.rmtree(stage, ignore_errors=True)
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
        record(
            event="capture_cleanup", staging_absent=stage is None or not stage.exists()
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(capture_manifest_path(capture(args.source, args.destination)))
