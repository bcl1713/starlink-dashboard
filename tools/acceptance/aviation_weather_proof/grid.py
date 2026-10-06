"""Bounded quantization and atomic publication of diagnostic geographic grids."""

from copy import deepcopy
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile

import numpy as np

from .model import ProductArtifact, file_hash, load_capture, capture_manifest_path

PUBLISHED_QUOTA_BYTES = 5 * 1024**3 // 2
STAGING_QUOTA_BYTES = 1024**3
RESERVE_BYTES = 512 * 1024**2
MAX_GENERATION_BYTES = 16 * 1024**2


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _validate(descriptor, components, mask):
    if descriptor.get("schema") != "aviation-weather-v1" or descriptor.get("representation") != "latlon-grid-v1":
        raise ValueError("unsupported grid schema/representation")
    geometry = descriptor["grid"]
    width, height = geometry["width"], geometry["height"]
    if type(width) is not int or type(height) is not int or not 1 <= width <= 720 or not 1 <= height <= 361:
        raise ValueError("invalid grid dimensions")
    for key, expected in (("longitude_start", -180), ("longitude_step", 0.5), ("latitude_start", 90), ("latitude_step", -0.5)):
        if geometry.get(key) != expected:
            raise ValueError("unsupported grid geometry")
    if not components or set(components) != set(descriptor["components"]):
        raise ValueError("component declarations must match arrays")
    if width * height * (2 * len(components) + 1) > MAX_GENERATION_BYTES:
        raise ValueError("grid generation quota exceeded before encoding")
    mask = np.asarray(mask)
    if mask.shape != (height, width) or not np.isin(mask, [0, 1, 2, 3]).all():
        raise ValueError("invalid grid mask shape/encoding")
    encoded = {}
    valid = mask == 0
    for name, array in components.items():
        if name == "mask" or not re.fullmatch(r"[a-z][a-z0-9_-]{0,40}", name):
            raise ValueError("component name must be confined")
        declaration = descriptor["components"][name]
        scale, offset = declaration["scale"], declaration["offset"]
        if not math.isfinite(scale) or scale <= 0 or not math.isfinite(offset):
            raise ValueError("invalid quantization scale/offset")
        if declaration.get("units") not in ("K", "m/s") or not isinstance(declaration.get("quantity"), str):
            raise ValueError("unsupported scientific quantity/units")
        array = np.asarray(array)
        if array.shape != mask.shape:
            raise ValueError("component shape mismatch")
        selected = array[valid]
        if not np.isfinite(selected).all():
            raise ValueError("valid component values must be finite")
        quantized = np.rint((selected - offset) / scale)
        if not np.isfinite(quantized).all() or (quantized < -32768).any() or (quantized > 32767).any():
            raise ValueError("quantization overflows Int16")
        output = np.zeros(mask.shape, dtype="<i2")
        output[valid] = quantized.astype("<i2")
        encoded[name] = output.tobytes()
    encoded["mask"] = mask.astype("u1").tobytes()
    return encoded


def write_grid(descriptor: dict, components: dict[str, np.ndarray], mask: np.ndarray, destination: Path) -> ProductArtifact:
    """Publish all payloads together; retain the original verified source receipt.

    Input capture_manifest_path is private and removed from the browser descriptor.
    The returned path names the replayable original manifest, including its objects.
    A parent-level lock serializes publication quota admission and final rename.
    """
    destination = Path(destination)
    if destination.exists():
        raise ValueError("grid destination already exists")
    descriptor = deepcopy(descriptor)
    encoded = _validate(descriptor, components, mask)
    capture = load_capture(Path(descriptor.pop("capture_manifest_path")))
    receipt = capture_manifest_path(capture)
    descriptor["capture_manifest_sha256"] = file_hash(receipt)
    descriptor["mask"] = {"encoding": {"0": "valid", "1": "outside-coverage", "2": "missing", "3": "quality-rejected"}}
    machine = {
        "schema": descriptor["schema"], "representation": descriptor["representation"],
        "grid": descriptor["grid"], "components": descriptor["components"],
        "mask": descriptor["mask"], "normalization_version": descriptor.get("normalization_version", "diagnostic-grid-v1"),
        "source_id": descriptor.get("source_id", capture.source), "vertical": descriptor.get("vertical"),
    }
    descriptor["product_id"] = hashlib.sha256(canonical(machine)).hexdigest()
    descriptor["instance_id"] = hashlib.sha256(canonical({
        "product_id": descriptor["product_id"], "sources": [o.sha256 for o in capture.objects],
        "run_at_ms": descriptor.get("run_at_ms"), "lead_seconds": descriptor.get("lead_seconds"),
        "valid_at_ms": descriptor.get("valid_at_ms"), "scan_start_ms": descriptor.get("scan_start_ms"),
        "scan_end_ms": descriptor.get("scan_end_ms"),
    })).hexdigest()
    for name, payload in encoded.items():
        entry = descriptor["mask"] if name == "mask" else descriptor["components"][name]
        entry.update(path=f"{name}.bin", sha256=hashlib.sha256(payload).hexdigest(), byte_size=len(payload), dtype="uint8" if name == "mask" else "int16-le")
    return publish_payloads(descriptor, {f"{name}.bin": payload for name, payload in encoded.items()}, receipt, destination)


def publish_payloads(descriptor: dict, payloads: dict[str, bytes], receipt: Path, destination: Path) -> ProductArtifact:
    """Atomically publish a bounded product under the shared parent quota lock.

    Grid and advisory payloads share admission, fsync, rename and cleanup. Receipt
    is the original verified manifest and never copied into the browser product.
    """
    destination = Path(destination)
    if destination.exists():
        raise ValueError("product destination already exists")
    if not payloads or any(not re.fullmatch(r"[a-z][a-z0-9_-]*\.(?:bin|geojson)", name) or not isinstance(payload, bytes) for name, payload in payloads.items()):
        raise ValueError("payload paths must be confined and bounded")
    metadata = canonical(descriptor) + b"\n"
    total = len(metadata) + sum(map(len, payloads.values()))
    if total > MAX_GENERATION_BYTES or total > STAGING_QUOTA_BYTES:
        raise ValueError("product staging/generation quota exceeded")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with (destination.parent / ".grid-quota.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if destination.exists():
            raise ValueError("product destination already exists")
        used = sum(p.stat().st_size for p in destination.parent.rglob("*") if p.is_file())
        if used + total > PUBLISHED_QUOTA_BYTES:
            raise ValueError("published grid quota exceeded")
        if shutil.disk_usage(destination.parent).free < RESERVE_BYTES + total:
            raise ValueError("insufficient disk reserve")
        stage = Path(tempfile.mkdtemp(prefix=".grid-stage-", dir=destination.parent))
        try:
            for name, payload in {**payloads, "descriptor.json": metadata}.items():
                with (stage / name).open("xb") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
            stage.rename(destination)
            parent_fd = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
    return ProductArtifact(destination / "descriptor.json", tuple(destination / name for name in payloads), receipt)
