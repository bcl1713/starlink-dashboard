"""Pressure coverage is resolved on source nodes before conservative sampling."""

import hashlib

import numpy as np
import pytest

from app.models.aviation_grid import GfsSelection
from tests.fixtures.gfs_fields import RUN, grib_bundle


def candidate(root, **kwargs):
    from app.services.aviation_weather.gfs.decode import decode_bundle
    from app.services.aviation_weather.gfs.grid import normalize_grid

    return normalize_grid(
        decode_bundle(grib_bundle(root / "source", **kwargs)),
        GfsSelection(),
        root / "candidate",
        clock=lambda: RUN / 1000,
    )


def test_grid_orientation_seam_poles_and_valid_zero(tmp_path):
    result = candidate(tmp_path)
    descriptor = result.descriptor
    assert descriptor.grid.width == 720 and descriptor.grid.height == 361
    for name, expected in (("u", 0), ("v", 1000), ("t", 685)):
        body = (result.directory / f"{name}.bin").read_bytes()
        values = np.frombuffer(body, dtype="<i2").reshape(361, 720)
        assert (values == expected).all()
        assert descriptor.buffers[name].sha256 == hashlib.sha256(body).hexdigest()
    assert (np.fromfile(result.directory / "mask.bin", dtype="u1") == 0).all()


def test_terrain_is_unknown_and_never_physical_zero(tmp_path):
    result = candidate(tmp_path, surface=40000)
    assert (np.fromfile(result.directory / "mask.bin", dtype="u1") == 1).all()


def test_missing_surface_and_any_contributor_propagate(tmp_path):
    from app.services.aviation_weather.gfs.decode import decode_bundle
    from app.services.aviation_weather.gfs.grid import normalize_grid

    fields = decode_bundle(grib_bundle(tmp_path / "source"))
    _sp, valid = fields.components[("sp", None)]
    valid[1, 0] = False
    result = normalize_grid(
        fields, GfsSelection(), tmp_path / "candidate", clock=lambda: RUN / 1000
    )
    mask = np.fromfile(result.directory / "mask.bin", dtype="u1").reshape(361, 720)
    # Source longitude 0 corresponds to target column 360; adjacent half-degree
    # samples depend on this missing source node, while longitude 180 stays valid.
    assert mask[180, 360] == 2
    assert mask[181, 361] == 2
    assert mask[180, 0] == 0


def test_quantization_overflow_rejects_entire_candidate(tmp_path):
    with pytest.raises(ValueError):
        _overflow(tmp_path)
    assert not (tmp_path / "candidate").exists()


def _overflow(tmp_path):
    from app.services.aviation_weather.gfs.decode import decode_bundle
    from app.services.aviation_weather.gfs.grid import normalize_grid

    fields = decode_bundle(grib_bundle(tmp_path / "source"))
    fields.components[("u", 50000)][0][:] = 400
    return normalize_grid(
        fields, GfsSelection(), tmp_path / "candidate", clock=lambda: RUN / 1000
    )


def test_source_and_vertical_identity_do_not_alias(tmp_path):
    first = candidate(tmp_path / "one")
    second = candidate(tmp_path / "two", surface=99999)
    assert first.descriptor.product_id == second.descriptor.product_id
    assert first.descriptor.instance_id != second.descriptor.instance_id


def test_reversed_source_scan_keeps_geographic_samples(tmp_path):
    from app.services.aviation_weather.gfs.decode import decode_bundle
    from app.services.aviation_weather.gfs.grid import normalize_grid

    reverse = {
        name: {
            "jScansPositively": 1,
            "iScansNegatively": 1,
            "latitudeOfFirstGridPointInDegrees": -90,
            "latitudeOfLastGridPointInDegrees": 90,
            "longitudeOfFirstGridPointInDegrees": 270,
            "longitudeOfLastGridPointInDegrees": 0,
        }
        for name in ("u", "v", "t", "sp")
    }
    candidates = []
    for name, overrides in (("forward", None), ("reverse", reverse)):
        bundle = grib_bundle(
            tmp_path / name / "source", overrides=overrides, coordinate_values=True
        )
        candidates.append(
            normalize_grid(
                decode_bundle(bundle),
                GfsSelection(),
                tmp_path / name / "grid",
                clock=lambda: RUN / 1000,
            )
        )
    assert {
        name: buffer.sha256 for name, buffer in candidates[0].descriptor.buffers.items()
    } == {
        name: buffer.sha256 for name, buffer in candidates[1].descriptor.buffers.items()
    }
    values = np.fromfile(candidates[0].directory / "u.bin", dtype="<i2").reshape(
        361, 720
    )
    assert values[180, 360] == 0  # equator, longitude 0
    assert values[0, 360] == 900  # north pole, longitude 0
    assert values[360, 360] == -900  # south pole, longitude 0
    assert values[180, 0] == 180  # equator, longitude 180
