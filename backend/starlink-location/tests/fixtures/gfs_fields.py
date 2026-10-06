"""Small actual GRIB messages with independently known global field values."""

import hashlib
from datetime import datetime, timezone

from app.models.aviation_grid import RangeRef, SourceBundle, SourceRef

RUN = int(datetime(2026, 10, 6, tzinfo=timezone.utc).timestamp() * 1000)


def grib_bundle(
    root,
    *,
    surface=100000,
    pressure=50000,
    overrides=None,
    coordinate_values=False,
    run_at_ms=RUN,
):
    import eccodes as ec
    import numpy as np

    root.mkdir(parents=True, exist_ok=True)
    paths, hashes, ranges = [], [], []
    run = datetime.fromtimestamp(run_at_ms / 1000, timezone.utc)
    for quantity, value in (("u", 0), ("v", 10), ("t", 280), ("sp", surface)):
        handle = ec.codes_grib_new_from_samples("regular_ll_sfc_grib2")
        try:
            values = {
                "Ni": 4,
                "Nj": 3,
                "latitudeOfFirstGridPointInDegrees": 90,
                "latitudeOfLastGridPointInDegrees": -90,
                "longitudeOfFirstGridPointInDegrees": 0,
                "longitudeOfLastGridPointInDegrees": 270,
                "iDirectionIncrementInDegrees": 90,
                "jDirectionIncrementInDegrees": 90,
                "dataDate": int(run.strftime("%Y%m%d")),
                "dataTime": int(run.strftime("%H%M")),
                "stepUnits": 1,
                "forecastTime": 6,
                "typeOfLevel": "surface" if quantity == "sp" else "isobaricInhPa",
                "level": 0 if quantity == "sp" else pressure // 100,
                "shortName": quantity,
            }
            values.update((overrides or {}).get(quantity, {}))
            for name, entry in values.items():
                ec.codes_set(handle, name, entry)
            field = np.full(12, value, dtype=float)
            ec.codes_set_values(handle, field)
            if coordinate_values and quantity == "u":
                field = (
                    ec.codes_get_array(handle, "latitudes") * 0.1
                    + np.remainder(ec.codes_get_array(handle, "longitudes"), 360) * 0.01
                )
            ec.codes_set_values(handle, field)
            path = root / f"{quantity}.grib2"
            with path.open("wb") as stream:
                ec.codes_write(handle, stream)
        finally:
            ec.codes_release(handle)
        body = path.read_bytes()
        paths.append(path)
        hashes.append(hashlib.sha256(body).hexdigest())
        ranges.append(
            RangeRef(
                SourceRef("fixture", '"fixed"', len(body)),
                0,
                len(body) - 1,
                quantity,
                None if quantity == "sp" else pressure,
            )
        )
    return SourceBundle(
        run_at_ms, 21600, tuple(ranges), tuple(paths), tuple(hashes), run_at_ms
    )
