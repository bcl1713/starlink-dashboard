"""Worker-only ecCodes boundary; no scientific import occurs in API processes."""

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.models.aviation_grid import SourceBundle


@dataclass(frozen=True)
class DecodedFields:
    bundle: SourceBundle
    run_at_ms: int
    lead_seconds: int
    latitudes: Any
    longitudes: Any
    components: dict
    terrain: Any = None


def _instant(date, clock):
    value = datetime.strptime(f"{date:08d}{clock:04d}", "%Y%m%d%H%M").replace(
        tzinfo=timezone.utc
    )
    return int(value.timestamp() * 1000)


def decode_bundle(bundle: SourceBundle) -> DecodedFields:
    import eccodes as ec
    import numpy as np

    if not 4 <= len(bundle.paths) <= 7 or not len(bundle.ranges) == len(
        bundle.paths
    ) == len(bundle.hashes):
        raise ValueError("Incomplete bounded scientific bundle")
    components, axes, vector_basis = {}, None, {}
    for ref, path, digest in zip(
        bundle.ranges, bundle.paths, bundle.hashes, strict=True
    ):
        if (
            path.stat().st_size > 32 * 1024**2
            or hashlib.sha256(path.read_bytes()).hexdigest() != digest
        ):
            raise ValueError("Scientific object hash/size mismatch")
        with path.open("rb", buffering=0) as stream:
            if stream.read(4) != b"GRIB":
                raise ValueError("Not a GRIB message")
            stream.seek(0)
            handle = ec.codes_grib_new_from_file(stream)
            if handle is None:
                raise ValueError("Missing scientific message")
            try:
                name = ec.codes_get(handle, "shortName")
                key = name, ref.pressure_pa
                if (
                    name != ref.quantity
                    or key in components
                    or name not in {"u", "v", "t", "sp"}
                ):
                    raise ValueError("Duplicate or unexpected scientific field")
                if ec.codes_get(handle, "gridType") != "regular_ll":
                    raise ValueError("Unsupported projected/rotated source geometry")
                units = "K" if name == "t" else "Pa" if name == "sp" else "m s**-1"
                if ec.codes_get(handle, "units") != units:
                    raise ValueError("Unsupported scientific units")
                expected_level = "surface" if name == "sp" else "isobaricInhPa"
                if ec.codes_get(handle, "typeOfLevel") != expected_level or (
                    name != "sp"
                    and ec.codes_get(handle, "level") * 100 != ref.pressure_pa
                ):
                    raise ValueError("Scientific vertical identity mismatch")
                run = _instant(
                    ec.codes_get(handle, "dataDate"), ec.codes_get(handle, "dataTime")
                )
                valid_time = _instant(
                    ec.codes_get(handle, "validityDate"),
                    ec.codes_get(handle, "validityTime"),
                )
                lead = int(ec.codes_get(handle, "endStep")) * 3600
                if (
                    ec.codes_get(handle, "stepType") != "instant"
                    or ec.codes_get(handle, "stepUnits") != 1
                    or run != bundle.run_at_ms
                    or lead != bundle.lead_seconds
                    or valid_time != run + lead * 1000
                ):
                    raise ValueError("Scientific model time mismatch")
                ni, nj = int(ec.codes_get(handle, "Ni")), int(
                    ec.codes_get(handle, "Nj")
                )
                if (
                    not 2 <= ni <= 1440
                    or not 2 <= nj <= 721
                    or ni * nj != ec.codes_get(handle, "numberOfDataPoints")
                    or ni * nj * (len(bundle.paths) + 6) * 8 > 256 * 1024**2
                ):
                    raise ValueError("Scientific expansion exceeds bounded dimensions")
                latitudes = ec.codes_get_array(handle, "latitudes")
                longitudes = np.remainder(ec.codes_get_array(handle, "longitudes"), 360)
                lat, lon = np.unique(latitudes), np.unique(longitudes)
                if (
                    len(lat) != nj
                    or len(lon) != ni
                    or not np.isclose(lat[0], -90)
                    or not np.isclose(lat[-1], 90)
                    or not np.allclose(np.diff(lat), 180 / (nj - 1), rtol=0, atol=1e-6)
                    or not np.allclose(np.diff(lon), 360 / ni, rtol=0, atol=1e-6)
                ):
                    raise ValueError("Incomplete global regular coordinates")
                order = np.lexsort((longitudes, latitudes))
                if not np.array_equal(
                    latitudes[order], np.repeat(lat, ni)
                ) or not np.array_equal(longitudes[order], np.tile(lon, nj)):
                    raise ValueError("Duplicate or incomplete coordinate scan")
                if axes is not None and (
                    not np.array_equal(lat, axes[0]) or not np.array_equal(lon, axes[1])
                ):
                    raise ValueError("Inconsistent source grids")
                axes = lat, lon
                values = ec.codes_get_values(handle)
                if len(values) != ni * nj:
                    raise ValueError("Scientific decoded dimension mismatch")
                validity = (
                    ec.codes_get_array(handle, "bitmap").astype(bool)
                    if ec.codes_get(handle, "bitmapPresent")
                    else np.ones(ni * nj, dtype=bool)
                )
                validity &= np.isfinite(values)
                if name == "sp":
                    validity &= (values > 0) & (values <= 120000)
                if name in {"u", "v"}:
                    basis = ec.codes_get(handle, "uvRelativeToGrid")
                    if basis not in (0, 1):
                        raise ValueError("Unknown vector basis")
                    vector_basis[key] = basis
                components[key] = (
                    values[order].reshape(nj, ni).astype("f4"),
                    validity[order].reshape(nj, ni),
                )
                if stream.read(1):
                    raise ValueError(
                        "Scientific object contains trailing bytes/messages"
                    )
            finally:
                ec.codes_release(handle)
    pressures = {pressure for name, pressure in components if name != "sp"}
    if set(components) != {
        (name, pressure) for pressure in pressures for name in ("u", "v", "t")
    } | {("sp", None)}:
        raise ValueError("Missing complete scientific triplet or surface pressure")
    if any(
        vector_basis[("u", pressure)] != vector_basis[("v", pressure)]
        for pressure in pressures
    ):
        raise ValueError("Inconsistent wind vector basis")
    return DecodedFields(
        bundle, bundle.run_at_ms, bundle.lead_seconds, axes[0], axes[1], components
    )
