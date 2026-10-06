"""Conservative source masks, global interpolation and one-time quantization."""

import hashlib
import json
import os
import shutil
import time
from dataclasses import asdict
from pathlib import Path

from app.models.aviation_grid import (
    HORIZONS,
    GfsSelection,
    GridCandidate,
    GridDescriptor,
)

from .decode import DecodedFields


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def normalize_grid(
    fields: DecodedFields,
    selection: GfsSelection,
    destination: Path,
    *,
    clock=time.time,
) -> GridCandidate:
    import numpy as np

    pressure = selection.pressure_pa
    components = {name: fields.components[(name, pressure)] for name in ("u", "v", "t")}
    surface, surface_valid = fields.components[("sp", None)]
    lat, lon = fields.latitudes, fields.longitudes
    target_lat = 90 - np.arange(361) * 0.5
    target_lon = np.remainder(-180 + np.arange(720) * 0.5 - lon[0], 360) + lon[0]
    yi = np.clip(np.searchsorted(lat, target_lat, side="right") - 1, 0, len(lat) - 2)
    yw = (target_lat - lat[yi]) / (lat[yi + 1] - lat[yi])
    extended_lon = np.append(lon, lon[0] + 360)
    xi = np.searchsorted(extended_lon, target_lon, side="right") - 1
    xw = (target_lon - extended_lon[xi]) / (extended_lon[xi + 1] - extended_lon[xi])
    missing = ~surface_valid.copy()
    terrain = surface_valid & (pressure > surface)
    for values, validity in components.values():
        missing |= ~validity | ~np.isfinite(values)
    mask = np.zeros((361, 720), dtype="u1")
    output = {name: np.zeros((361, 720), dtype="f8") for name in components}
    # Terrain and missing contributors are checked BEFORE interpolation; a
    # surface interpolated above terrain cannot make below-ground data valid.
    for row, rw in ((yi, 1 - yw), (yi + 1, yw)):
        for column, cw in ((xi, 1 - xw), ((xi + 1) % len(lon), xw)):
            weight = rw[:, None] * cw[None, :]
            contributors = weight > 0
            indices = row[:, None], column[None, :]
            mask[contributors & terrain[indices]] = 1
            mask[contributors & missing[indices]] = 2
            for name, (values, _) in components.items():
                output[name] += np.where(
                    contributors & ~missing[indices] & ~terrain[indices],
                    values[indices] * weight,
                    0,
                )
    # Missing takes precedence over terrain independently of iteration order.
    for row, rw in ((yi, 1 - yw), (yi + 1, yw)):
        for column, cw in ((xi, 1 - xw), ((xi + 1) % len(lon), xw)):
            mask[
                (rw[:, None] * cw[None, :] > 0) & missing[row[:, None], column[None, :]]
            ] = 2
    encoded = {"mask": mask.tobytes()}
    for name, values in output.items():
        quantized = np.rint((values[mask == 0] - (273.15 if name == "t" else 0)) / 0.01)
        if (
            not np.isfinite(quantized).all()
            or (quantized < -32768).any()
            or (quantized > 32767).any()
        ):
            raise ValueError("Scientific quantization exceeds Int16")
        array = np.zeros(mask.shape, dtype="<i2")
        array[mask == 0] = quantized.astype("<i2")
        encoded[name] = array.tobytes()
    geometry = {
        "width": 720,
        "height": 361,
        "longitude_start": -180.0,
        "latitude_start": 90.0,
        "longitude_step": 0.5,
        "latitude_step": -0.5,
        "mask_encoding": "uint8-validity-v1",
        "components": [
            {"quantity": quantity, "unit": unit, "scale": 0.01, "offset": offset}
            for quantity, unit, offset in (
                ("wind-east", "m/s", 0.0),
                ("wind-north", "m/s", 0.0),
                ("air-temperature", "K", 273.15),
            )
        ],
    }
    machine = {
        "version": "gfs-regular-ll-v1",
        "grid": geometry,
        "vertical": {"kind": "pressure", "pressure_pa": float(pressure)},
        "mask": "shared-conservative-uvt",
    }
    product = hashlib.sha256(canonical(machine)).hexdigest()
    instance = hashlib.sha256(
        canonical(
            {
                "product": product,
                "hashes": fields.bundle.hashes,
                "run": fields.run_at_ms,
                "lead": fields.lead_seconds,
                "buffers": {
                    name: hashlib.sha256(body).hexdigest()
                    for name, body in encoded.items()
                },
            }
        )
    ).hexdigest()
    descriptor = GridDescriptor.model_validate(
        {
            "schema": "aviation-weather-v1",
            "representation": "latlon-grid-v1",
            "normalization_version": "gfs-regular-ll-v1",
            "product_id": product,
            "instance_id": instance,
            "run_at_ms": fields.run_at_ms,
            "lead_seconds": fields.lead_seconds,
            "valid_at_ms": fields.run_at_ms + fields.lead_seconds * 1000,
            "retrieved_at_ms": fields.bundle.retrieved_at_ms,
            "generated_at_ms": max(fields.bundle.retrieved_at_ms, int(clock() * 1000)),
            "vertical": machine["vertical"],
            "grid": geometry,
            "buffers": {
                name: {
                    "path": f"/api/aviation-weather/v1/products/{instance}/{name}.bin",
                    "sha256": hashlib.sha256(body).hexdigest(),
                    "byte_length": len(body),
                    "dtype": "uint8" if name == "mask" else "int16-le",
                }
                for name, body in encoded.items()
            },
        }
    )
    destination.mkdir(parents=True, exist_ok=False)
    try:
        for name, body in encoded.items():
            (destination / f"{name}.bin").write_bytes(body)
        (destination / "grid.json").write_bytes(
            canonical(descriptor.model_dump(by_alias=True))
        )
        leads = sorted(
            {
                lead
                for lead in (fields.bundle.available_leads or (fields.lead_seconds,))
                if lead % 3600 == 0 and lead // 3600 in HORIZONS
            }
        )
        if fields.lead_seconds not in leads:
            raise ValueError("Chosen lead absent from actual inventory")
        index = leads.index(fields.lead_seconds)
        # Targets at a midpoint select the earlier instant. Bounds are UTC
        # milliseconds; exclude a lower midpoint by one millisecond.
        lower = fields.run_at_ms + (
            500 * (leads[index - 1] + leads[index]) + 1 if index else 0
        )
        upper = fields.run_at_ms + (
            500 * (leads[index] + leads[index + 1])
            if index + 1 < len(leads)
            else 172800000
        )
        (destination / "admission.json").write_bytes(
            canonical(
                {
                    "selection": selection.model_dump(),
                    "target_from_ms": lower,
                    "target_to_ms": upper,
                }
            )
        )
        private = destination / "lineage"
        private.mkdir()
        for i, path in enumerate(fields.bundle.paths):
            shutil.copyfile(path, private / f"{i}.grib2")
        (private / "source.json").write_bytes(
            canonical(
                {
                    "run_at_ms": fields.run_at_ms,
                    "lead_seconds": fields.lead_seconds,
                    "ranges": [asdict(ref) for ref in fields.bundle.ranges],
                    "hashes": fields.bundle.hashes,
                }
            )
        )
        for path in destination.rglob("*"):
            if path.is_file():
                with path.open("rb") as stream:
                    os.fsync(stream.fileno())
        for path in (private, destination):
            fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        return GridCandidate(descriptor, destination)
    except BaseException:
        shutil.rmtree(destination)
        raise
