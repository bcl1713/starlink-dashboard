"""Scientific buffers must be fully identified before browser acquisition."""

import copy

import pytest
from pydantic import ValidationError


def descriptor():
    root = "/api/aviation-weather/v1/products/" + "b" * 64
    components = [
        {"quantity": "wind-east", "unit": "m/s", "scale": 0.01, "offset": 0.0},
        {"quantity": "wind-north", "unit": "m/s", "scale": 0.01, "offset": 0.0},
        {"quantity": "air-temperature", "unit": "K", "scale": 0.01, "offset": 273.15},
    ]
    return {
        "schema": "aviation-weather-v1",
        "representation": "latlon-grid-v1",
        "product_id": "a" * 64,
        "instance_id": "b" * 64,
        "normalization_version": "gfs-regular-ll-v1",
        "run_at_ms": 1791244800000,
        "lead_seconds": 21600,
        "valid_at_ms": 1791266400000,
        "retrieved_at_ms": 1791244800000,
        "generated_at_ms": 1791244800000,
        "vertical": {"kind": "pressure", "pressure_pa": 50000.0},
        "grid": {
            "width": 720,
            "height": 361,
            "longitude_start": -180.0,
            "latitude_start": 90.0,
            "longitude_step": 0.5,
            "latitude_step": -0.5,
            "mask_encoding": "uint8-validity-v1",
            "components": components,
        },
        "buffers": {
            name: {
                "path": f"{root}/{name}.bin",
                "sha256": "c" * 64,
                "byte_length": 259920 if name == "mask" else 519840,
                "dtype": "uint8" if name == "mask" else "int16-le",
            }
            for name in ("u", "v", "t", "mask")
        },
    }


def test_descriptor_admits_complete_pressure_generation():
    from app.models.aviation_grid import GridDescriptor

    result = GridDescriptor.model_validate(descriptor())
    assert sum(v.byte_length for v in result.buffers.values()) == 1819440
    assert result.valid_at_ms == 1791266400000


@pytest.mark.parametrize(
    "mutation",
    [
        ("path", "https://evil.test/u.bin"),
        ("path", "../u.bin"),
        ("path", "/api/aviation-weather/v1/products/" + "d" * 64 + "/u.bin"),
        ("byte_length", 519839),
        ("dtype", "uint8"),
        ("sha256", "bad"),
    ],
)
def test_rejects_unbound_or_truncated_buffers(mutation):
    from app.models.aviation_grid import GridDescriptor

    data = descriptor()
    data["buffers"]["u"][mutation[0]] = mutation[1]
    with pytest.raises(ValidationError):
        GridDescriptor.model_validate(data)


def test_rejects_model_time_or_component_mismatch():
    from app.models.aviation_grid import GridDescriptor

    for key, value in (("valid_at_ms", 1791266400001), ("lead_seconds", -1)):
        data = descriptor()
        data[key] = value
        with pytest.raises(ValidationError):
            GridDescriptor.model_validate(data)
    data = copy.deepcopy(descriptor())
    data["grid"]["components"][0]["quantity"] = "air-temperature"
    with pytest.raises(ValidationError):
        GridDescriptor.model_validate(data)


def test_public_descriptor_declares_shared_conservative_mask_scope():
    from app.models.aviation_grid import GridDescriptor

    assert (
        GridDescriptor.model_validate(descriptor()).model_dump()["mask_scope"]
        == "shared-conservative-uvt"
    )
