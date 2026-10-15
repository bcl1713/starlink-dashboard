"""Envelope admission must reject ambiguity before any payload acquisition."""

import copy

import pytest
from pydantic import ValidationError

from app.models.aviation_weather import AviationCatalog, WeatherProduct

NOW = 1791244800000


def product(**changes):
    data = {
        "state": "ready",
        "layer_id": "terminal-observations",
        "product_type": "metar-speci",
        "representation": "station-v1",
        "source_id": "awc",
        "provenance": "AWC station reports",
        "attribution": [{"label": "NOAA AWC", "url": "https://aviationweather.gov/"}],
        "time_kind": "observation",
        "method_kind": "reported",
        "observed_at_ms": NOW - 600000,
        "issued_at_ms": None,
        "scan_start_ms": None,
        "scan_end_ms": None,
        "validity_kind": "instant",
        "valid_at_ms": NOW - 600000,
        "valid_from_ms": None,
        "valid_to_ms": None,
        "run_at_ms": None,
        "lead_seconds": None,
        "vertical": {"kind": "surface"},
        "coverage": {
            "generation": "snapshot-1",
            "expires_at_ms": NOW + 600000,
            "mask_encoding": "feature-collection-v1",
            "missing_meaning": "unknown-not-clear",
            "feed_completeness": "unknown",
        },
        "generated_at_ms": NOW,
        "retrieved_at_ms": NOW,
        "fresh_until_ms": NOW + 300000,
        "expires_at_ms": NOW + 600000,
        "product_id": "a" * 64,
        "instance_id": "b" * 64,
        "payload": {
            "path": "/api/aviation-weather/v1/products/" + "b" * 64 + "/stations.json",
            "sha256": "c" * 64,
            "content_type": "application/geo+json",
            "encoded_bytes": 100,
            "decoded_bytes": 1000,
            "gpu_bytes": 1000,
        },
        "radar": None,
        "grid": None,
    }
    data.update(changes)
    return data


def test_observation_contract_preserves_unknown_coverage():
    result = WeatherProduct.model_validate(product())
    assert result.coverage.missing_meaning == "unknown-not-clear"
    assert result.run_at_ms is None
    assert result.observed_at_ms == NOW - 600000


@pytest.mark.parametrize(
    "changes",
    [
        {"time_kind": "analysis"},
        {"method_kind": "numerical-model"},
        {"run_at_ms": NOW},
        {"valid_at_ms": None},
        {"valid_from_ms": NOW},
        {"observed_at_ms": NOW + 60001},
        {"expires_at_ms": NOW},
        {"fresh_until_ms": NOW + 600001},
        {"representation": "unknown"},
        {"representation": "latlon-grid-v1"},
        {"instance_id": None},
        {"payload": None},
        {"state": "off"},
        {"surprise": True},
        {"observed_at_ms": True},
        {"scan_start_ms": NOW},
    ],
)
def test_rejects_incoherent_observation(changes):
    with pytest.raises(ValidationError):
        WeatherProduct.model_validate(product(**changes))


@pytest.mark.parametrize(
    "path",
    [
        "https://evil.test/data",
        "//evil.test/data",
        "/api/private/data",
        "/api/aviation-weather/v1/products/../data",
        "/api/aviation-weather/v1/products/%2e%2e/data",
        "/api/aviation-weather/v1/products/" + "b" * 64 + "/x?token=secret",
        "/api/aviation-weather/v1/products/" + "d" * 64 + "/stations.json",
    ],
)
def test_payload_identity_and_namespace_are_admitted_before_fetch(path):
    data = product()
    data["payload"]["path"] = path
    with pytest.raises(ValidationError):
        WeatherProduct.model_validate(data)


@pytest.mark.parametrize(
    "field,limit",
    [
        ("encoded_bytes", 16 * 1024**2),
        ("decoded_bytes", 32 * 1024**2),
        ("gpu_bytes", 16 * 1024**2),
    ],
)
def test_allocation_bounds(field, limit):
    data = product()
    data["payload"][field] = limit + 1
    with pytest.raises(ValidationError):
        WeatherProduct.model_validate(data)


def test_numerical_model_run_lead_and_vertical_identity():
    data = product(
        time_kind="forecast",
        method_kind="numerical-model",
        observed_at_ms=None,
        run_at_ms=NOW - 3600000,
        lead_seconds=7200,
        valid_at_ms=NOW + 3600000,
        vertical={"kind": "pressure", "pressure_pa": 50000.0},
    )
    assert WeatherProduct.model_validate(data).vertical.pressure_pa == 50000
    for changes in [
        {"valid_at_ms": NOW},
        {"lead_seconds": None},
        {"time_kind": "analysis"},
        {"observed_at_ms": NOW},
    ]:
        with pytest.raises(ValidationError):
            WeatherProduct.model_validate({**data, **changes})
    data.update(time_kind="analysis", lead_seconds=0, valid_at_ms=NOW - 3600000)
    assert WeatherProduct.model_validate(data).time_kind == "analysis"


def test_interval_forecasts_are_distinct_and_finite():
    data = product(
        time_kind="forecast",
        observed_at_ms=None,
        issued_at_ms=NOW,
        validity_kind="interval",
        valid_at_ms=None,
        valid_from_ms=NOW,
        valid_to_ms=NOW + 600000,
        vertical={"kind": "not-applicable"},
    )
    assert WeatherProduct.model_validate(data).run_at_ms is None
    for changes in [
        {"valid_to_ms": NOW},
        {"valid_at_ms": NOW},
        {"run_at_ms": NOW},
        {"issued_at_ms": None},
    ]:
        with pytest.raises(ValidationError):
            WeatherProduct.model_validate({**data, **changes})


def test_catalog_rejects_duplicate_layers_or_unknown_schema():
    data = {
        "schema": "aviation-weather-v1",
        "generated_at_ms": NOW,
        "settings_revision": 0,
        "products": [product()],
    }
    assert len(AviationCatalog.model_validate(data).products) == 1
    for changes in [
        {"schema": "future-v2"},
        {"products": [product()] * 2},
        {"products": [product()] * 17},
    ]:
        with pytest.raises(ValidationError):
            AviationCatalog.model_validate({**data, **changes})


def test_grid_requires_valid_geometry_units_and_allocation():
    data = product(
        representation="latlon-grid-v1",
        product_type="air-temperature",
        grid={
            "width": 720,
            "height": 361,
            "longitude_start": -180.0,
            "latitude_start": 90.0,
            "longitude_step": 0.5,
            "latitude_step": -0.5,
            "mask_encoding": "uint8-validity-v1",
            "components": [
                {
                    "quantity": "air-temperature",
                    "unit": "K",
                    "scale": 0.01,
                    "offset": 250.0,
                }
            ],
        },
    )
    data["coverage"]["mask_encoding"] = "uint8-validity-v1"
    data["payload"].update(
        decoded_bytes=779760, gpu_bytes=779760, content_type="application/json"
    )
    assert WeatherProduct.model_validate(data).grid.height == 361
    for key, value in [
        ("width", 721),
        ("latitude_step", 0.5),
        ("mask_encoding", "absence-rgba-v1"),
    ]:
        changed = copy.deepcopy(data)
        changed["grid"][key] = value
        with pytest.raises(ValidationError):
            WeatherProduct.model_validate(changed)
    for changes in [
        {"unit": "degC"},
        {"scale": 0.0},
        {"quantity": "wind-east", "unit": "K"},
    ]:
        changed = copy.deepcopy(data)
        changed["grid"]["components"][0].update(changes)
        with pytest.raises(ValidationError):
            WeatherProduct.model_validate(changed)
    data["payload"]["decoded_bytes"] = 1000
    with pytest.raises(ValidationError):
        WeatherProduct.model_validate(data)


@pytest.mark.parametrize("field", ["radar_tile_template", "coverage_tile_template"])
def test_backend_rejects_forged_radar_paths_before_catalog_admission(field):
    from app.models.overview_weather import WeatherManifest
    from app.services.aviation_weather.catalog import radar_product
    from app.services.overview_weather.rainviewer import RainViewerAdapter

    capability = RainViewerAdapter().normalized()
    manifest = WeatherManifest(
        **capability,
        state="ready",
        settings_revision=0,
        generated_at_ms=NOW,
        frame_time_ms=NOW - 600000,
        coverage_token=20732,
        coverage_expires_at_ms=1791331200000,
        radar_tile_template=f'/api/overview-weather/radar/1791244200/{{z}}/{{x}}/{{y}}.png?product_id={capability["product_id"]}',
        coverage_tile_template=f'/api/overview-weather/coverage/20732/{{z}}/{{x}}/{{y}}.png?product_id={capability["product_id"]}',
    )
    assert radar_product(manifest, NOW).state == "ready"
    forged = manifest.model_copy(update={field: "/api/private/exfiltrate"})
    with pytest.raises(ValidationError):
        radar_product(forged, NOW)
