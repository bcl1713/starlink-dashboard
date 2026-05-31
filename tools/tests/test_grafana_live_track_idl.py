import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_DIR = (
    REPO_ROOT / "monitoring" / "grafana" / "provisioning" / "dashboards"
)

HEMISPHERE_HISTORY_TARGETS = {
    "E": "starlink_dish_latitude_degrees and starlink_dish_longitude_degrees < 0",
    "F": "starlink_dish_longitude_degrees < 0",
    "E_EAST": "starlink_dish_latitude_degrees and starlink_dish_longitude_degrees >= 0",
    "F_EAST": "starlink_dish_longitude_degrees >= 0",
}

FALLBACK_GUARDS = {
    "E": "count_over_time((starlink_dish_longitude_degrees < 0)[$__range:]) > 0",
    "F": "count_over_time((starlink_dish_longitude_degrees < 0)[$__range:]) > 0",
    "E_EAST": "count_over_time((starlink_dish_longitude_degrees >= 0)[$__range:]) > 0",
    "F_EAST": "count_over_time((starlink_dish_longitude_degrees >= 0)[$__range:]) > 0",
}
UNSPLIT_HISTORY_FALLBACKS = {
    "E": "starlink_dish_latitude_degrees",
    "F": "starlink_dish_longitude_degrees",
    "E_EAST": "starlink_dish_latitude_degrees",
    "F_EAST": "starlink_dish_longitude_degrees",
}
HEMISPHERE_HISTORY_TARGETS_WITH_FALLBACK = {
    ref_id: (
        f"({expr}) or ({UNSPLIT_HISTORY_FALLBACKS[ref_id]} "
        f"unless {FALLBACK_GUARDS[ref_id]})"
    )
    for ref_id, expr in HEMISPHERE_HISTORY_TARGETS.items()
}

DASHBOARD_LIVE_MAPS = [
    (
        "fullscreen-overview.json",
        "Current Position",
        "Position History - Western Hemisphere",
        "Position History - Eastern Hemisphere",
        "latitude_history",
        "longitude_history",
    ),
    (
        "overview.json",
        "Live Position Map",
        "Historical Route - Western Hemisphere",
        "Historical Route - Eastern Hemisphere",
        "lat_history",
        "lon_history",
    ),
    (
        "position-movement.json",
        "Live Position Map (Large)",
        "Historical Route - Western Hemisphere",
        "Historical Route - Eastern Hemisphere",
        "lat_history",
        "lon_history",
    ),
]


def _dashboard(filename: str) -> dict:
    return json.loads((DASHBOARD_DIR / filename).read_text())


def _panel_by_title(dashboard: dict, title: str) -> dict:
    panels = [panel for panel in dashboard["panels"] if panel.get("title") == title]
    assert len(panels) == 1
    return panels[0]


def _target_exprs(panel: dict) -> dict[str, str]:
    return {
        target["refId"]: target["expr"]
        for target in panel["targets"]
        if target.get("refId") in HEMISPHERE_HISTORY_TARGETS
    }


def _route_layers_by_name(panel: dict) -> dict[str, dict]:
    return {
        layer["name"]: layer
        for layer in panel["options"]["layers"]
        if layer.get("type") == "route"
    }


def _join_filters(panel: dict) -> set[str]:
    return {
        transformation.get("filter", {}).get("options")
        for transformation in panel.get("transformations", [])
        if transformation.get("id") == "joinByField"
    }


def test_live_history_track_queries_are_split_by_hemisphere_for_idl() -> None:
    for filename, panel_title, *_ in DASHBOARD_LIVE_MAPS:
        panel = _panel_by_title(_dashboard(filename), panel_title)

        target_exprs = _target_exprs(panel)
        assert target_exprs == HEMISPHERE_HISTORY_TARGETS_WITH_FALLBACK
        for ref_id, base_expr in HEMISPHERE_HISTORY_TARGETS.items():
            assert base_expr in target_exprs[ref_id]


def test_no_idl_selected_timeframe_keeps_a_drawable_history_track() -> None:
    for filename, panel_title, *_ in DASHBOARD_LIVE_MAPS:
        panel = _panel_by_title(_dashboard(filename), panel_title)

        for ref_id, expr in _target_exprs(panel).items():
            assert ref_id in HEMISPHERE_HISTORY_TARGETS
            assert "vector(0/0)" not in expr, (
                f"{filename} {panel_title} target {ref_id} must not use a "
                "NaN-only fallback; Grafana can receive a defined frame but "
                "still render no visible live track."
            )
            assert UNSPLIT_HISTORY_FALLBACKS[ref_id] in expr
            assert f"unless {FALLBACK_GUARDS[ref_id]}" in expr


def test_live_history_track_layers_are_split_by_hemisphere_for_idl() -> None:
    for (
        filename,
        panel_title,
        west_layer_name,
        east_layer_name,
        latitude_field,
        longitude_field,
    ) in DASHBOARD_LIVE_MAPS:
        panel = _panel_by_title(_dashboard(filename), panel_title)
        route_layers = _route_layers_by_name(panel)

        west_history = route_layers[west_layer_name]
        east_history = route_layers[east_layer_name]

        assert west_history["filterByRefId"] == "E"
        assert west_history["filterData"] == {
            "id": "byRefId",
            "options": "joinByField-E-F",
        }
        assert west_history["location"] == {
            "mode": "coords",
            "latitude": latitude_field,
            "longitude": longitude_field,
        }

        assert east_history["filterByRefId"] == "E_EAST"
        assert east_history["filterData"] == {
            "id": "byRefId",
            "options": "joinByField-E_EAST-F_EAST",
        }
        assert east_history["location"] == west_history["location"]


def test_live_history_transformations_join_each_hemisphere_independently() -> None:
    for filename, panel_title, *_ in DASHBOARD_LIVE_MAPS:
        panel = _panel_by_title(_dashboard(filename), panel_title)

        assert {
            "/^(?:E|F)$/",
            "/^(?:E_EAST|F_EAST)$/",
        } <= _join_filters(panel)
