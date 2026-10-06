"""Independent geographic fixtures pin units, masks and XYZ reprojection."""

import hashlib
from dataclasses import replace

import h5py
import numpy as np
import pytest
import rasterio
from acceptance.weather_detail_comparison.generate import (
    MAX_LATITUDE,
    generate,
    open_raster,
    region_keys,
    tile_bounds,
)
from acceptance.weather_detail_comparison.model import Snapshot, TileKey
from PIL import Image
from rasterio.transform import from_bounds


def saved(path, source="mrms"):
    return Snapshot(
        source,
        "PrecipRate" if source == "mrms" else "RATE",
        1791253800,
        1791253860,
        "mm/h",
        "EPSG:3857",
        "https://mrms.ncep.noaa.gov/a",
        "test",
        "synthetic test fixture",
        path,
        hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def raster(tmp_path, values):
    path = tmp_path / "rates.tif"
    key = TileKey(2, 2, 1)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=values.shape[1],
        height=values.shape[0],
        count=1,
        dtype="float32",
        crs="EPSG:3857",
        transform=from_bounds(*tile_bounds(key), values.shape[1], values.shape[0]),
    ) as output:
        output.write(values.astype("float32"), 1)
        output.update_tags(
            1,
            GRIB_ELEMENT="PrecipRate",
            GRIB_UNIT="[mm/hr]",
            GRIB_VALID_TIME="1791253800",
            GRIB_FORECAST_SECONDS="0",
        )
    return saved(path), key


def pixels(tmp_path, value):
    snapshot, key = raster(tmp_path, np.full((16, 16), value))
    pair = generate(snapshot, (key,), tmp_path)[key]
    return np.array(Image.open(pair.radar_path)), np.array(
        Image.open(pair.absence_path)
    )


def test_zero_rain_is_covered(tmp_path):
    rain, absent = pixels(tmp_path, 0)
    assert np.all(rain[:, :, 3] == 0)
    assert np.all(absent[:, :, 3] == 0)


@pytest.mark.parametrize("value", [-1, -3, float("nan")])
def test_nodata_is_absent(tmp_path, value):
    rain, absent = pixels(tmp_path, value)
    assert np.all(absent[:, :, 3] == 255)
    assert np.all(rain[:, :, 3] == 0)


def test_orientation_and_precipitation_are_independent(tmp_path):
    values = np.array([[0, 1], [10, -1]], dtype="float32")
    snapshot, key = raster(tmp_path, values)
    pair = generate(snapshot, (key,), tmp_path)[key]
    rain = np.array(Image.open(pair.radar_path))
    absent = np.array(Image.open(pair.absence_path))
    assert rain[128, 128, 3] == 0  # northwest clear
    assert rain[128, 384, 3] > 0  # northeast light rain
    assert rain[384, 128, 3] > 0  # southwest heavier rain
    assert absent[384, 384, 3] == 255  # southeast unknown
    assert not np.array_equal(rain[128, 384], rain[384, 128])


def test_reprojection_never_fills_missing_coverage(tmp_path):
    snapshot, key = raster(tmp_path, np.ones((16, 16)))
    unsupported = TileKey(2, 3, 1)
    pairs = generate(snapshot, (key, unsupported), tmp_path)
    assert np.all(np.array(Image.open(pairs[unsupported].absence_path))[:, :, 3] == 255)


def test_source_metadata_rejects_forecast_and_timestamp_mismatch(tmp_path):
    snapshot, _ = raster(tmp_path, np.ones((16, 16)))
    with pytest.raises(ValueError, match="timestamp"):
        open_raster(replace(snapshot, observed_utc=1791253860))
    with rasterio.open(snapshot.local_path, "r+") as output:
        output.update_tags(1, GRIB_FORECAST_SECONDS="600")
    with pytest.raises(ValueError, match="forecast"):
        open_raster(snapshot)


def test_undetect_is_covered_zero(tmp_path):
    path = tmp_path / "opera.h5"
    with h5py.File(path, "w") as h:
        h.create_group("what").attrs.update(
            date=np.bytes_("20261006"),
            time=np.bytes_("023000"),
            object=np.bytes_("COMP"),
        )
        h.create_group("where").attrs.update(
            projdef=np.bytes_("+proj=longlat +datum=WGS84"),
            UL_lon=0.0,
            UL_lat=60.0,
            xscale=1.0,
            yscale=1.0,
            xsize=2,
            ysize=2,
        )
        h.create_group("dataset1/data1/what").attrs.update(
            quantity=np.bytes_("RATE"), gain=2.0, offset=1.0, nodata=255.0, undetect=0.0
        )
        h.create_dataset(
            "dataset1/data1/data", data=np.array([[0, 255], [2, 3]], dtype="uint8")
        )
    rates = open_raster(saved(path, "opera"))
    assert rates.valid.tolist() == [[True, False], [True, True]]
    assert rates.values[0, 0] == 0
    assert rates.values[1, 0] == 5


def test_antimeridian_and_latitude_keys_are_bounded():
    assert region_keys(40, 180, 7) == region_keys(40, -180, 7)
    assert len(region_keys(40, 179.9, 7)) == 8
    assert {k.x for k in region_keys(40, 179.9, 7)} & {0, 127}
    assert all(0 <= k.y < 128 for k in region_keys(MAX_LATITUDE, 0, 7))
    with pytest.raises(ValueError):
        region_keys(90, 0, 7)


def test_neighboring_tile_bounds_share_exact_edge():
    left = tile_bounds(TileKey(7, 63, 42))
    right = tile_bounds(TileKey(7, 64, 42))
    assert left[2] == right[0]
    assert left[1] == right[1]
    assert left[3] == right[3]
