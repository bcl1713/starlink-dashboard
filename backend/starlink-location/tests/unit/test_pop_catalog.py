"""Validation, content fingerprints, configuration, and UTC contracts."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import ConfigManager
from app.models.config import SimulationConfig
from app.services.pop.catalog import DEFAULT_CATALOG_PATH, load_catalog
from app.services.pop.models import PopCrossing, PopForecast, PopTransition


def site(**changes):
    result = {
        "id": "test",
        "city": "Test",
        "country": "US",
        "latitude": 0.0,
        "longitude": 0.0,
        "aliases": [],
        "source": "Operator",
        "coordinate_source": "https://www.geonames.org/",
    }
    result.update(changes)
    return result


def write_catalog(tmp_path, sites):
    path = tmp_path / "pops.json"
    path.write_text(json.dumps({"sites": sites}))
    return path


def test_default_catalog_has_six_sourced_identities():
    catalog = load_catalog(DEFAULT_CATALOG_PATH)
    assert {s.id for s in catalog.sites} == {
        "los-angeles",
        "ashburn",
        "dallas",
        "sydney",
        "frankfurt",
        "tokyo",
    }
    assert all("Starshield" in s.source and "email" in s.source for s in catalog.sites)
    assert all(
        s.coordinate_source.startswith("https://www.geonames.org/")
        for s in catalog.sites
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"id": ""},
        {"id": "invalid ID"},
        {"city": " "},
        {"country": ""},
        {"latitude": 91},
        {"latitude": float("nan")},
        {"longitude": 181},
        {"longitude": float("inf")},
        {"source": ""},
        {"coordinate_source": ""},
    ],
)
def test_invalid_site_rejects_entire_catalog(tmp_path, changes):
    with pytest.raises(ValueError):
        load_catalog(
            write_catalog(tmp_path, [site(id="valid", longitude=30), site(**changes)])
        )


@pytest.mark.parametrize(
    "other",
    [
        {"city": "Other", "longitude": 20},
        {"id": "other", "city": "Other"},
        {"id": "other", "city": " test ", "longitude": 20},
    ],
)
def test_duplicate_id_location_or_identity_rejects_catalog(tmp_path, other):
    with pytest.raises(ValueError):
        load_catalog(write_catalog(tmp_path, [site(), site(**other)]))


@pytest.mark.parametrize("sites", [[], [{"id": "incomplete"}]])
def test_empty_or_incomplete_catalog_rejected(tmp_path, sites):
    with pytest.raises(ValueError):
        load_catalog(write_catalog(tmp_path, sites))


def test_fingerprint_ignores_json_order_but_tracks_edits(tmp_path):
    a, b = site(), site(id="other", city="Other", longitude=20)
    path = write_catalog(tmp_path, [a, b])
    original = load_catalog(path)
    path.write_text(
        json.dumps({"sites": [dict(reversed(list(b.items()))), a]}, indent=4)
    )
    assert load_catalog(path).fingerprint == original.fingerprint
    b["longitude"] = 21
    write_catalog(tmp_path, [a, b])
    assert load_catalog(path).fingerprint != original.fingerprint
    with pytest.raises(ValidationError):
        original.sites[0].latitude = 5


def test_catalog_path_default_yaml_and_environment_override(tmp_path, monkeypatch):
    assert SimulationConfig().pop.catalog_path == DEFAULT_CATALOG_PATH
    path = tmp_path / "config.yaml"
    path.write_text("pop:\n  catalog_path: /tmp/custom-pops.json\n")
    assert ConfigManager.load_from_file(path).pop.catalog_path == Path(
        "/tmp/custom-pops.json"
    )
    monkeypatch.setenv("STARLINK_POP_CATALOG_PATH", "/tmp/env-pops.json")
    assert ConfigManager.load_from_dict({}).pop.catalog_path == Path(
        "/tmp/env-pops.json"
    )
    assert ConfigManager.load_from_file(path).pop.catalog_path == Path(
        "/tmp/env-pops.json"
    )


def test_transition_serializes_aware_time_as_utc_and_rejects_naive():
    crossing = PopCrossing(
        id="x",
        from_pop_id="a",
        to_pop_id="b",
        segment_index=0,
        fraction=0.5,
        latitude=0,
        longitude=0,
        distance_meters=1,
    )
    center = datetime(2026, 1, 1, 10, tzinfo=timezone(timedelta(hours=2)))
    transition = PopTransition(
        crossing=crossing,
        crossing_utc=center,
        window_start_utc=center - timedelta(seconds=300),
        window_end_utc=center + timedelta(seconds=300),
    )
    forecast = PopForecast(
        revision="r",
        catalog_fingerprint="f",
        status="ready",
        reason=None,
        transitions=(transition,),
    )
    assert (
        json.loads(forecast.model_dump_json())["transitions"][0]["crossing_utc"]
        == "2026-01-01T08:00:00Z"
    )
    with pytest.raises(ValidationError):
        PopTransition(
            crossing=crossing,
            crossing_utc=center.replace(tzinfo=None),
            window_start_utc=center,
            window_end_utc=center,
        )
