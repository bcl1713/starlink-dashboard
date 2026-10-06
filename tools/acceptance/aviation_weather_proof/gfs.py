"""Offline ecCodes normalization of the pinned regular-geographic GFS proof."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import time

import eccodes as ec
import numpy as np

from .grid import write_grid
from .model import CaptureManifest, ProductArtifact, capture_manifest_path, object_path


def _utc(date, clock):
    return datetime.strptime(f"{date:08d}{clock:04d}", "%Y%m%d%H%M").replace(tzinfo=timezone.utc)


def _decode(capture):
    fields = {}
    identity = None
    latitudes = longitudes = None
    for obj in capture.objects:
        path = object_path(capture, obj)
        # ecCodes reads the underlying file descriptor. A buffered magic read
        # can leave that descriptor at EOF despite Python's buffered seek(0).
        with path.open("rb", buffering=0) as stream:
            if stream.read(4) != b"GRIB":
                continue  # Index is provenance, not a scientific field.
            stream.seek(0)
            handle = ec.codes_grib_new_from_file(stream)
            if handle is None:
                raise ValueError("missing GRIB message")
            try:
                name = ec.codes_get(handle, "shortName")
                if name not in ("u", "v", "t") or name in fields:
                    raise ValueError("expected unique GFS U/V/T fields")
                if ec.codes_get(handle, "gridType") != "regular_ll":
                    raise ValueError("projected/rotated GFS grids unsupported by this proof")
                units = ec.codes_get(handle, "units")
                if units != ("K" if name == "t" else "m s**-1"):
                    raise ValueError("unsupported source units")
                if ec.codes_get(handle, "typeOfLevel") != "isobaricInhPa" or ec.codes_get(handle, "level") != 500:
                    raise ValueError("expected native pressure 500 hPa")
                run = _utc(ec.codes_get(handle, "dataDate"), ec.codes_get(handle, "dataTime"))
                if ec.codes_get(handle, "stepType") != "instant" or ec.codes_get(handle, "stepUnits") != 1:
                    raise ValueError("expected instant forecast with hourly lead")
                lead = int(ec.codes_get(handle, "endStep")) * 3600
                valid = _utc(ec.codes_get(handle, "validityDate"), ec.codes_get(handle, "validityTime"))
                if lead < 0 or valid != run + timedelta(seconds=lead):
                    raise ValueError("incoherent model time identity")
                ni, nj = int(ec.codes_get(handle, "Ni")), int(ec.codes_get(handle, "Nj"))
                if not 2 <= ni <= 1440 or not 2 <= nj <= 721:
                    raise ValueError("source dimensions outside proof decoder cap")
                if ec.codes_get(handle, "numberOfDataPoints") != ni * nj:
                    raise ValueError("source dimensions disagree with point count")
                current = (run, lead, valid, ni, nj)
                if identity is not None and current != identity:
                    raise ValueError("inconsistent run/lead/grid identity")
                identity = current
                lats = ec.codes_get_array(handle, "latitudes")
                lons = ec.codes_get_array(handle, "longitudes")
                values = ec.codes_get_values(handle)
                if len(values) != ni * nj or len(lats) != len(values) or len(lons) != len(values):
                    raise ValueError("source scan dimensions do not match decoded values")
                if latitudes is not None and (not np.array_equal(lats, latitudes) or not np.array_equal(lons, longitudes)):
                    raise ValueError("inconsistent coordinate/scan geometry")
                latitudes, longitudes = lats, lons
                bitmap = ec.codes_get_array(handle, "bitmap").astype(bool) if ec.codes_get(handle, "bitmapPresent") else np.ones(len(values), dtype=bool)
                bitmap &= np.isfinite(values)
                relative = int(ec.codes_get(handle, "uvRelativeToGrid"))
                if relative not in (0, 1):
                    raise ValueError("unknown vector reference")
                # regular_ll grid east/north IS geographic east/north. Scanning
                # affects serialization, not the basis; rotation angle is zero.
                fields[name] = (values, bitmap, relative)
                if stream.read(1):
                    raise ValueError("object must contain exactly one GRIB message")
            finally:
                ec.codes_release(handle)
    if set(fields) != {"u", "v", "t"} or identity is None:
        raise ValueError("capture lacks complete GFS U/V/T")
    if fields["u"][2] != fields["v"][2]:
        raise ValueError("inconsistent vector basis")
    return fields, identity, latitudes, longitudes


def _regularize(fields, latitudes, longitudes, ni, nj):
    """Coordinate arrays, rather than assumptions about scan bits, order nodes."""
    lon = np.remainder(longitudes, 360)
    lat_axis = np.unique(latitudes)
    lon_axis = np.unique(lon)
    if len(lat_axis) != nj or len(lon_axis) != ni or not np.allclose(np.diff(lat_axis), np.diff(lat_axis)[0]) or not np.allclose(np.diff(lon_axis), 360 / ni):
        raise ValueError("source is not a complete regular global geographic grid")
    if not np.isclose(lat_axis[0], -90) or not np.isclose(lat_axis[-1], 90):
        raise ValueError("source must cover both poles")
    order = np.lexsort((lon, latitudes))
    expected_lat = np.repeat(lat_axis, ni)
    expected_lon = np.tile(lon_axis, nj)
    if not np.array_equal(latitudes[order], expected_lat) or not np.array_equal(lon[order], expected_lon):
        raise ValueError("duplicate/incomplete source coordinates")
    return {name: (v[order].reshape(nj, ni), m[order].reshape(nj, ni)) for name, (v, m, _) in fields.items()}, lat_axis, lon_axis


def _regrid(fields, lat, lon):
    target_lat = 90 - np.arange(361) * 0.5
    target_lon = np.remainder(-180 + np.arange(720) * 0.5 - lon[0], 360) + lon[0]
    yi = np.clip(np.searchsorted(lat, target_lat, side="right") - 1, 0, len(lat) - 2)
    yw = (target_lat - lat[yi]) / (lat[yi + 1] - lat[yi])
    extended_lon = np.append(lon, lon[0] + 360)
    xi = np.searchsorted(extended_lon, target_lon, side="right") - 1
    xw = (target_lon - extended_lon[xi]) / (extended_lon[xi + 1] - extended_lon[xi])
    mask = np.zeros((361, 720), dtype="u1")
    output = {}
    for name, (values, valid) in fields.items():
        result = np.zeros((361, 720))
        available = np.ones((361, 720), dtype=bool)
        for row, row_weight in ((yi, 1 - yw), (yi + 1, yw)):
            for column, column_weight in ((xi, 1 - xw), ((xi + 1) % len(lon), xw)):
                weight = row_weight[:, None] * column_weight[None, :]
                contributing = weight > 0
                cell_valid = valid[row[:, None], column[None, :]]
                available &= ~contributing | cell_valid
                result += np.where(contributing & cell_valid, values[row[:, None], column[None, :]] * weight, 0)
        mask[~available] = 2
        output[name] = result
    return output, mask


def normalize_gfs(capture: CaptureManifest, destination: Path) -> ProductArtifact:
    if capture.source != "gfs":
        raise ValueError("expected GFS capture")
    receipt = capture_manifest_path(capture)
    fields, (run, lead, valid, ni, nj), lats, lons = _decode(capture)
    regular, lat, lon = _regularize(fields, lats, lons, ni, nj)
    components, mask = _regrid(regular, lat, lon)
    descriptor = {
        "schema": "aviation-weather-v1", "representation": "latlon-grid-v1",
        "normalization_version": "diagnostic-gfs-regular-ll-v1", "diagnostic": True,
        "source_id": "noaa-ncep-gfs", "layer_id": "gfs-wind-temperature-500hpa",
        "product_type": "model-wind-temperature", "capture_manifest_path": str(receipt),
        "attribution": list(capture.attribution), "provenance": {"source_objects": [
            {"sha256": o.sha256, "byte_size": o.byte_size, "url": o.url, "byte_range": o.byte_range} for o in capture.objects
        ], "source_grid": {"width": ni, "height": nj, "grid_type": "regular_ll"}, "vector_rotation": "geographic-basis-identity"},
        "time_kind": "analysis" if lead == 0 else "forecast", "method_kind": "numerical-model",
        "validity_kind": "instant", "valid_at_ms": int(valid.timestamp() * 1000),
        "valid_from_ms": None, "valid_to_ms": None,
        "run_at_ms": int(run.timestamp() * 1000), "lead_seconds": lead,
        "observed_at_ms": None, "issued_at_ms": None, "scan_start_ms": None, "scan_end_ms": None,
        "retrieved_at_ms": capture.captured_at_ms, "generated_at_ms": int(time.time() * 1000),
        "vertical": {"kind": "pressure", "value": 500, "units": "hPa", "reference": "isobaric", "derivation": "native-pressure-surface"},
        "coverage": {"kind": "global-grid", "interpolation": "bilinear-all-contributors-valid", "missing": "mask"},
        "grid": {"width": 720, "height": 361, "longitude_start": -180, "longitude_step": 0.5, "latitude_start": 90, "latitude_step": -0.5},
        "components": {
            "u": {"quantity": "eastward-wind", "units": "m/s", "offset": 0, "scale": 0.01},
            "v": {"quantity": "northward-wind", "units": "m/s", "offset": 0, "scale": 0.01},
            "t": {"quantity": "air-temperature", "units": "K", "offset": 273.15, "scale": 0.01},
        },
    }
    return write_grid(descriptor, components, mask, destination)
