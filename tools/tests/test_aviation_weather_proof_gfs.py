"""Scientific identity, coordinate orientation and complete artifact publication."""

import importlib
import json

import eccodes as ec
import numpy as np
import pytest

from acceptance.aviation_weather_proof.model import (
    CaptureManifest, CapturedObject, file_hash, load_capture, write_manifest,
)


@pytest.fixture
def api():
    return importlib.import_module("acceptance.aviation_weather_proof.gfs")


def capture(tmp_path, *, reverse=False, missing=False, change=None, relative=False):
    """Actual encoded 2x2 GRIBs; landmark values are hand assigned geographically."""
    source = tmp_path / "source"
    source.mkdir()
    objects = []
    for name, param, values in (
        ("u", 131, [0, 2, 3, 4]),
        ("v", 132, [0, -2, -3, -4]),
        ("t", 130, [273.15, 275.15, 276.15, 277.15]),
    ):
        handle = ec.codes_grib_new_from_samples("regular_ll_pl_grib2")
        try:
            settings = {
                "Ni": 2, "Nj": 2,
                "latitudeOfFirstGridPointInDegrees": -90 if reverse else 90,
                "latitudeOfLastGridPointInDegrees": 90 if reverse else -90,
                "longitudeOfFirstGridPointInDegrees": 180 if reverse else 0,
                "longitudeOfLastGridPointInDegrees": 0 if reverse else 180,
                "iDirectionIncrementInDegrees": 180,
                "jDirectionIncrementInDegrees": 180,
                "iScansNegatively": int(reverse), "jScansPositively": int(reverse),
                "uvRelativeToGrid": int(relative),
                "dataDate": 20261006, "dataTime": 0, "forecastTime": 6,
                "typeOfLevel": "isobaricInhPa", "level": 500, "paramId": param,
                "packingType": "grid_simple", "bitsPerValue": 24,
            }
            if change and name == change[0]:
                settings[change[1]] = change[2]
            for key, value in settings.items():
                ec.codes_set(handle, key, value)
            if missing:
                ec.codes_set(handle, "bitmapPresent", 1)
                ec.codes_set(handle, "missingValue", 9999)
                values[3] = 9999
            if reverse:
                values = values[::-1]
            ec.codes_set_values(handle, values)
            path = source / f"{name}.grib2"
            with path.open("wb") as stream:
                ec.codes_write(handle, stream)
        finally:
            ec.codes_release(handle)
        objects.append(CapturedObject(
            "https://noaa-gfs-bdp-pds.s3.amazonaws.com/fixture", None, path.name,
            file_hash(path), path.stat().st_size,
        ))
    manifest = CaptureManifest("gfs", 1791288000000, tuple(objects), ("NOAA fixture",))
    write_manifest(manifest, source / "capture.json")
    return load_capture(source / "capture.json")


def decoded(artifact):
    descriptor = json.loads(artifact.descriptor_path.read_text())
    shape = (descriptor["grid"]["height"], descriptor["grid"]["width"])
    values = {}
    for name, component in descriptor["components"].items():
        values[name] = np.fromfile(artifact.descriptor_path.parent / component["path"], "<i2").reshape(shape) * component["scale"] + component["offset"]
    mask = np.fromfile(artifact.descriptor_path.parent / descriptor["mask"]["path"], "u1").reshape(shape)
    return descriptor, values, mask


@pytest.mark.parametrize("reverse", [False, True])
def test_scan_orientation_and_seam(api, tmp_path, reverse):
    # Swapping N/S rows, reversing scan columns, or treating longitude 0 as -180 fails.
    artifact = api.normalize_gfs(capture(tmp_path, reverse=reverse), tmp_path / "product")
    descriptor, values, mask = decoded(artifact)
    assert descriptor["grid"] == {"width": 720, "height": 361, "longitude_start": -180, "longitude_step": 0.5, "latitude_start": 90, "latitude_step": -0.5}
    assert values["u"][0, 0] == 2
    assert values["u"][0, 360] == 0
    assert values["u"][360, 0] == 4
    assert values["u"][360, 360] == 3
    assert values["u"][0, 180] == 1
    assert values["u"][0, 540] == 1
    assert values["u"][0, 719] == 1.99
    assert np.all(mask == 0)


def test_valid_zero_vs_missing(api, tmp_path):
    # Missing contributors cannot turn into a valid zero, even at adjacent interpolated nodes.
    artifact = api.normalize_gfs(capture(tmp_path, missing=True), tmp_path / "product")
    _, values, mask = decoded(artifact)
    assert values["u"][0, 360] == values["v"][0, 360] == 0
    assert mask[0, 360] == 0
    assert mask[360, 0] == 2
    assert mask[359, 1] == 2
    assert mask[0, 0] == 0  # A zero-weight missing neighbor is not a contributor.


def test_model_time_identity(api, tmp_path):
    descriptor, _, _ = decoded(api.normalize_gfs(capture(tmp_path), tmp_path / "product"))
    assert descriptor["run_at_ms"] == 1791244800000
    assert descriptor["lead_seconds"] == 21600
    assert descriptor["valid_at_ms"] == 1791266400000
    assert descriptor["valid_at_ms"] == descriptor["run_at_ms"] + 1000 * descriptor["lead_seconds"]
    assert descriptor["time_kind"] == "forecast"


def test_pressure_is_not_flight_level(api, tmp_path):
    descriptor, _, _ = decoded(api.normalize_gfs(capture(tmp_path), tmp_path / "product"))
    assert descriptor["vertical"] == {"kind": "pressure", "value": 500, "units": "hPa", "reference": "isobaric", "derivation": "native-pressure-surface"}


@pytest.mark.parametrize("key,value", [("forecastTime", 9), ("level", 700), ("Ni", 3), ("paramId", 157)])
def test_mismatched_scientific_fields_fail_atomically(api, tmp_path, key, value):
    manifest = capture(tmp_path, change=("v", key, value))
    with pytest.raises(ValueError):
        api.normalize_gfs(manifest, tmp_path / "product")
    assert not (tmp_path / "product").exists()


def test_grid_relative_regular_lonlat_vectors(api, tmp_path):
    _, values, _ = decoded(api.normalize_gfs(capture(tmp_path, relative=True, reverse=True), tmp_path / "product"))
    assert values["u"][0, 0] == 2
    assert values["v"][0, 0] == -2


def writer_descriptor(manifest):
    from acceptance.aviation_weather_proof.model import capture_manifest_path
    return {
        "schema": "aviation-weather-v1", "representation": "latlon-grid-v1",
        "capture_manifest_path": str(capture_manifest_path(manifest)),
        "grid": {"width": 2, "height": 2, "longitude_start": -180, "longitude_step": 0.5, "latitude_start": 90, "latitude_step": -0.5},
        "components": {"t": {"quantity": "brightness-temperature", "units": "K", "offset": 273.15, "scale": 0.01}},
    }


def test_quantization_bounds(tmp_path):
    grid = importlib.import_module("acceptance.aviation_weather_proof.grid")
    descriptor = writer_descriptor(capture(tmp_path))
    temperatures = np.array([[273.15, 273.154], [273.146, 273.16]])
    artifact = grid.write_grid(descriptor, {"t": temperatures}, np.zeros((2, 2), dtype=np.uint8), tmp_path / "ok")
    _, values, _ = decoded(artifact)
    assert np.max(np.abs(values["t"] - temperatures)) <= 0.005
    assert np.fromfile(tmp_path / "ok" / "t.bin", "<i2").tolist() == [0, 0, 0, 1]
    temperatures[0, 0] = 700
    with pytest.raises(ValueError, match="Int16"):
        grid.write_grid(descriptor, {"t": temperatures}, np.zeros((2, 2), dtype=np.uint8), tmp_path / "overflow")
    assert not (tmp_path / "overflow").exists()
    assert not list(tmp_path.glob(".grid-stage-*"))


@pytest.mark.parametrize("mask", [np.array([[4, 0], [0, 0]]), np.array([[0.5, 0], [0, 0]]), np.zeros((1, 2))])
def test_writer_rejects_invalid_masks_before_publication(tmp_path, mask):
    grid = importlib.import_module("acceptance.aviation_weather_proof.grid")
    descriptor = writer_descriptor(capture(tmp_path))
    with pytest.raises(ValueError):
        grid.write_grid(descriptor, {"t": np.zeros((2, 2))}, mask, tmp_path / "product")
    assert not (tmp_path / "product").exists()


def test_writer_masks_nonfinite_and_cannot_replace_complete_product(tmp_path):
    grid = importlib.import_module("acceptance.aviation_weather_proof.grid")
    descriptor = writer_descriptor(capture(tmp_path))
    values = np.array([[273.15, np.nan], [np.inf, 273.15]])
    mask = np.array([[0, 2], [3, 1]], dtype=np.uint8)
    artifact = grid.write_grid(descriptor, {"t": values}, mask, tmp_path / "product")
    assert artifact.capture_manifest_path.is_file()
    assert decoded(artifact)[2].tolist() == [[0, 2], [3, 1]]
    before = artifact.descriptor_path.read_bytes()
    with pytest.raises(ValueError, match="exists"):
        grid.write_grid(descriptor, {"t": values}, mask, tmp_path / "product")
    assert artifact.descriptor_path.read_bytes() == before
    with pytest.raises(ValueError, match="finite"):
        grid.write_grid(descriptor, {"t": values}, np.zeros((2, 2), dtype=np.uint8), tmp_path / "invalid")
    assert not (tmp_path / "invalid").exists()


def test_writer_enforces_published_quota(tmp_path, monkeypatch):
    grid = importlib.import_module("acceptance.aviation_weather_proof.grid")
    descriptor = writer_descriptor(capture(tmp_path))
    monkeypatch.setattr(grid, "PUBLISHED_QUOTA_BYTES", 1)
    with pytest.raises(ValueError, match="quota"):
        grid.write_grid(descriptor, {"t": np.full((2, 2), 273.15)}, np.zeros((2, 2), dtype=np.uint8), tmp_path / "product")
    assert not (tmp_path / "product").exists()


def test_independent_reference_sampler_at_seam_poles_and_between_nodes(api, tmp_path):
    reference = importlib.import_module("acceptance.aviation_weather_proof.reference")
    artifact = api.normalize_gfs(capture(tmp_path), tmp_path / "product")
    # Literal geographic landmarks and off-node interpolation; no normalizer index helpers.
    assert reference.sample_grid(artifact.descriptor_path, 180, 90)["values"]["u"] == 2
    assert reference.sample_grid(artifact.descriptor_path, 0, -90)["values"]["u"] == 3
    assert reference.sample_grid(artifact.descriptor_path, -90, 0)["values"]["u"] == 2.25
    assert reference.sample_grid(artifact.descriptor_path, 0.25, 90)["values"]["u"] == pytest.approx(0.005)
    assert reference.sample_grid(artifact.descriptor_path, 0, 90)["values"]["u"] == 0


def test_independent_reference_source_comparison(api, tmp_path):
    reference = importlib.import_module("acceptance.aviation_weather_proof.reference")
    manifest = capture(tmp_path)
    artifact = api.normalize_gfs(manifest, tmp_path / "product")
    samples = reference.compare_gfs(manifest, artifact.descriptor_path, [(0, 90), (-180, -90)])
    assert samples[0]["source_values"] == pytest.approx({"u": 0, "v": 0, "t": 273.15}, abs=1e-5)
    assert samples[1]["source_values"] == pytest.approx({"u": 4, "v": -4, "t": 277.15}, abs=1e-5)
    assert samples[0]["quantization_tolerance"] == {"u": 0.005, "v": 0.005, "t": 0.005}
    assert samples[0]["resampling_tolerance"] == {"u": 0, "v": 0, "t": 0}


def test_reference_keeps_missing_distinct_from_physical_zero(api, tmp_path):
    reference = importlib.import_module("acceptance.aviation_weather_proof.reference")
    artifact = api.normalize_gfs(capture(tmp_path, missing=True), tmp_path / "product")
    missing = reference.sample_grid(artifact.descriptor_path, -180, -90)
    assert missing["mask"] == 2
    assert missing["values"] == {"u": None, "v": None, "t": None}
    # Source regridding allows zero-weight missing neighbors, but normalized
    # sampling validates every corner in its own enclosing output stencil.
    assert reference.sample_grid(artifact.descriptor_path, 0, 90)["mask"] == 2


def test_source_oracle_catches_common_shift_in_published_coordinate_metadata(api, tmp_path):
    reference = importlib.import_module("acceptance.aviation_weather_proof.reference")
    manifest = capture(tmp_path)
    artifact = api.normalize_gfs(manifest, tmp_path / "product")
    descriptor = json.loads(artifact.descriptor_path.read_text())
    # Simulate a longitude-origin error that a shared UV/index oracle would copy.
    descriptor["grid"]["longitude_start"] = 0
    artifact.descriptor_path.write_text(json.dumps(descriptor))
    with pytest.raises(ValueError, match="mismatch"):
        reference.compare_gfs(manifest, artifact.descriptor_path, [(0, 90)])


def test_writer_rejects_reserved_mask_component(tmp_path):
    grid = importlib.import_module("acceptance.aviation_weather_proof.grid")
    descriptor = writer_descriptor(capture(tmp_path))
    descriptor["components"]["mask"] = descriptor["components"].pop("t")
    with pytest.raises(ValueError, match="name"):
        grid.write_grid(descriptor, {"mask": np.full((2, 2), 273.15)}, np.zeros((2, 2), dtype=np.uint8), tmp_path / "product")
    assert not (tmp_path / "product").exists()


def test_writer_failure_during_payload_write_removes_staging(tmp_path, monkeypatch):
    grid = importlib.import_module("acceptance.aviation_weather_proof.grid")
    descriptor = writer_descriptor(capture(tmp_path))
    def failed_fsync(fd):
        raise OSError("simulated disk failure")
    monkeypatch.setattr(grid.os, "fsync", failed_fsync)
    with pytest.raises(OSError, match="disk failure"):
        grid.write_grid(descriptor, {"t": np.full((2, 2), 273.15)}, np.zeros((2, 2), dtype=np.uint8), tmp_path / "product")
    assert not (tmp_path / "product").exists()
    assert not list(tmp_path.glob(".grid-stage-*"))


def test_writer_product_identity_includes_quantization_and_source(tmp_path):
    grid = importlib.import_module("acceptance.aviation_weather_proof.grid")
    manifest = capture(tmp_path)
    descriptor = writer_descriptor(manifest)
    values = {"t": np.full((2, 2), 273.15)}
    mask = np.zeros((2, 2), dtype=np.uint8)
    first = decoded(grid.write_grid(descriptor, values, mask, tmp_path / "first"))[0]
    descriptor["attribution"] = ["Changed prose"]
    second = decoded(grid.write_grid(descriptor, values, mask, tmp_path / "second"))[0]
    assert first["product_id"] == second["product_id"]
    assert first["instance_id"] == second["instance_id"]
    descriptor["components"]["t"]["scale"] = 0.02
    third = decoded(grid.write_grid(descriptor, values, mask, tmp_path / "third"))[0]
    assert first["product_id"] != third["product_id"]
    assert first["instance_id"] != third["instance_id"]
    assert "capture_manifest_path" not in third


def test_writer_rejects_overbudget_components_before_encoding(tmp_path):
    grid = importlib.import_module("acceptance.aviation_weather_proof.grid")
    descriptor = writer_descriptor(capture(tmp_path))
    descriptor["grid"].update(width=720, height=361)
    descriptor["components"] = {f"t{i}": descriptor["components"]["t"] for i in range(40)}
    # Small arrays deliberately fail shape checks if budget preflight is absent.
    with pytest.raises(ValueError, match="generation quota"):
        grid.write_grid(descriptor, {key: np.zeros((1, 1)) for key in descriptor["components"]}, np.zeros((361, 720), dtype=np.uint8), tmp_path / "product")
    assert not (tmp_path / "product").exists()


@pytest.mark.parametrize("longitude,latitude", [(179.75, 90), (-179.25, 90), (-180, 89)])
def test_reference_partial_grid_does_not_wrap_across_uncovered_world(tmp_path, longitude, latitude):
    grid = importlib.import_module("acceptance.aviation_weather_proof.grid")
    reference = importlib.import_module("acceptance.aviation_weather_proof.reference")
    descriptor = writer_descriptor(capture(tmp_path))
    artifact = grid.write_grid(descriptor, {"t": np.full((2, 2), 273.15)}, np.zeros((2, 2), dtype=np.uint8), tmp_path / "product")
    assert reference.sample_grid(artifact.descriptor_path, 180, 90)["values"] == {"t": 273.15}
    outside = reference.sample_grid(artifact.descriptor_path, longitude, latitude)
    assert outside["mask"] == 1
    assert outside["values"] == {"t": None}
    assert outside["contributors"] == []


@pytest.mark.parametrize("mask,longitude,latitude", [
    ([[0, 2], [0, 0]], -180, 90),
    ([[0, 2], [0, 0]], -180, 89.75),
    ([[0, 0], [3, 0]], -180, 90),
    ([[0, 0], [3, 0]], -179.75, 90),
    ([[0, 0], [0, 1]], -180, 90),
])
def test_reference_requires_all_stencil_corners_even_with_zero_weight(tmp_path, mask, longitude, latitude):
    grid = importlib.import_module("acceptance.aviation_weather_proof.grid")
    reference = importlib.import_module("acceptance.aviation_weather_proof.reference")
    descriptor = writer_descriptor(capture(tmp_path))
    artifact = grid.write_grid(descriptor, {"t": np.full((2, 2), 273.15)}, np.array(mask, dtype=np.uint8), tmp_path / "product")
    sampled = reference.sample_grid(artifact.descriptor_path, longitude, latitude)
    assert sampled["mask"] == max(max(row) for row in mask)
    assert sampled["values"] == {"t": None}


@pytest.mark.parametrize("longitude,latitude", [(-179.5, 90), (-179.5, 89.5), (-179.75, 89.5)])
def test_reference_partial_boundary_clamps_stencil_without_unrelated_corners(tmp_path, longitude, latitude):
    grid = importlib.import_module("acceptance.aviation_weather_proof.grid")
    reference = importlib.import_module("acceptance.aviation_weather_proof.reference")
    descriptor = writer_descriptor(capture(tmp_path))
    artifact = grid.write_grid(descriptor, {"t": np.full((2, 2), 273.15)}, np.array([[2, 0], [0, 0]], dtype=np.uint8), tmp_path / "product")
    sampled = reference.sample_grid(artifact.descriptor_path, longitude, latitude)
    assert sampled["mask"] == 0
    assert sampled["values"] == {"t": 273.15}


def test_reference_full_grid_seam_validates_zero_weight_wrapped_neighbor(tmp_path):
    grid = importlib.import_module("acceptance.aviation_weather_proof.grid")
    reference = importlib.import_module("acceptance.aviation_weather_proof.reference")
    descriptor = writer_descriptor(capture(tmp_path))
    descriptor["grid"].update(width=720)
    mask = np.zeros((2, 720), dtype=np.uint8)
    mask[0, 0] = 2
    artifact = grid.write_grid(descriptor, {"t": np.full((2, 720), 273.15)}, mask, tmp_path / "product")
    sampled = reference.sample_grid(artifact.descriptor_path, 179.5, 90)
    assert sampled["mask"] == 2
    assert sampled["values"] == {"t": None}
