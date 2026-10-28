"""Backout removes only the additive selection key, preserving saved content."""

import importlib.util
from copy import deepcopy
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "overview_backout", Path(__file__).parents[1] / "overview_preset_backout.py"
)
backout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backout)


def test_backout_preserves_versions_weather_custom_bundles_and_original():
    original = {
        "next_flight_events_only": True,
        "future_config": {"keep": "unchanged"},
        "operator_presets": {
            name: {
                "version": 7,
                "settings": {"legend_enabled": False, "next_flight_events_only": True},
                "weather_visibility": {"radar": True},
            }
            for name in ("normal", "communications", "weather", "customer")
        },
    }
    before = deepcopy(original)
    prepared = backout.prepare_payload(original)
    assert original == before
    expected = deepcopy(before)
    expected.pop("next_flight_events_only")
    for preset in expected["operator_presets"].values():
        preset["settings"].pop("next_flight_events_only")
    assert prepared == expected
    assert backout.prepare_payload(prepared) == prepared
