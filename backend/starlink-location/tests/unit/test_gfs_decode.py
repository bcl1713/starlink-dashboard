"""Production ecCodes boundary validates actual messages, never decoded mocks."""

import hashlib
from dataclasses import replace

import pytest

from tests.fixtures.gfs_fields import grib_bundle


def test_actual_global_fields_preserve_zero_and_order_by_coordinates(tmp_path):
    from app.services.aviation_weather.gfs.decode import decode_bundle

    result = decode_bundle(grib_bundle(tmp_path))
    assert result.latitudes.tolist() == [-90, 0, 90]
    assert result.longitudes.tolist() == [0, 90, 180, 270]
    values, valid = result.components[("u", 50000)]
    assert values.dtype.name == "float32"
    assert valid.all() and (values == 0).all()
    assert result.run_at_ms == result.bundle.run_at_ms


@pytest.mark.parametrize(
    "overrides",
    [
        {"u": {"dataDate": 20261005}},
        {"v": {"forecastTime": 3}},
        {"t": {"level": 300}},
        {"v": {"uvRelativeToGrid": 1}},
        {"t": {"shortName": "r"}},
    ],
    ids=["run", "lead", "pressure", "basis", "quantity"],
)
def test_inconsistent_actual_metadata_is_rejected(tmp_path, overrides):
    from app.services.aviation_weather.gfs.decode import decode_bundle

    with pytest.raises(ValueError):
        decode_bundle(grib_bundle(tmp_path, overrides=overrides))


def test_duplicate_or_trailing_message_and_hash_change_rejected(tmp_path):
    from app.services.aviation_weather.gfs.decode import decode_bundle

    bundle = grib_bundle(tmp_path)
    path = bundle.paths[0]
    for suffix in (b"junk", path.read_bytes()):
        original = path.read_bytes()
        path.write_bytes(original + suffix)
        hashes = (hashlib.sha256(path.read_bytes()).hexdigest(), *bundle.hashes[1:])
        with pytest.raises(ValueError):
            decode_bundle(replace(bundle, hashes=hashes))
        path.write_bytes(original)
    path.write_bytes(path.read_bytes() + b"junk")
    with pytest.raises(ValueError):
        decode_bundle(bundle)
