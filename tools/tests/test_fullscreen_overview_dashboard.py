import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_PATH = (
    REPO_ROOT
    / "monitoring"
    / "grafana"
    / "provisioning"
    / "dashboards"
    / "fullscreen-overview.json"
)
CORE_MAP_LAYERS = {
    "Current Position",
    "Planned Route (KML) - Western Hemisphere",
    "Planned Route (KML) - Eastern Hemisphere",
    "MissionEvents",
    "Satellites",
}
RADAR_LAYER_NAME = "Weather Radar (RainViewer)"
RAINVIEWER_RADAR_TILE_URL = "http://localhost:8000/api/weather/radar/rainviewer/{z}/{x}/{y}.png"
HCX_COMM_LAYER_TOKENS = {"CommKaOverlay", "HCX"}
HCX_COMM_LAYER_SOURCES = {"commka.geojson"}
EXPECTED_CLOCK_DEFAULTS = {
    "UTC (Zulu)": "UTC",
    "Omaha": "America/Chicago",
    "Washington DC": "America/New_York",
    "Tokyo": "Asia/Tokyo",
}


def _fullscreen_overview_dashboard() -> dict:
    return json.loads(DASHBOARD_PATH.read_text())


def _current_position_layers() -> list[dict]:
    dashboard = _fullscreen_overview_dashboard()
    geomap_panels = [
        panel
        for panel in dashboard["panels"]
        if panel.get("type") == "geomap"
        and panel.get("title") == "Current Position"
    ]
    assert len(geomap_panels) == 1
    return geomap_panels[0]["options"]["layers"]


def _layers_by_name() -> dict[str, dict]:
    return {layer["name"]: layer for layer in _current_position_layers()}


def _clock_panels_by_title() -> dict[str, dict]:
    dashboard = _fullscreen_overview_dashboard()
    return {
        panel["title"]: panel
        for panel in dashboard["panels"]
        if panel.get("type") == "grafana-clock-panel"
    }


def _panel_by_title(title: str) -> dict:
    dashboard = _fullscreen_overview_dashboard()
    panels = [
        panel for panel in dashboard["panels"] if panel.get("title") == title
    ]
    assert len(panels) == 1
    return panels[0]


def _target_by_ref_id(panel: dict, ref_id: str) -> dict:
    targets = [
        target for target in panel["targets"] if target.get("refId") == ref_id
    ]
    assert len(targets) == 1
    return targets[0]


def _field_override_by_name(panel: dict, field_name: str) -> dict:
    matches = [
        override
        for override in panel["fieldConfig"]["overrides"]
        if override["matcher"] == {"id": "byName", "options": field_name}
    ]
    assert len(matches) == 1
    return matches[0]


def test_fullscreen_overview_dashboard_json_is_valid() -> None:
    dashboard = _fullscreen_overview_dashboard()

    assert dashboard["uid"] == "starlink-fullscreen"
    assert dashboard["title"] == "Fullscreen Overview"


def test_fullscreen_overview_has_only_mission_planner_link() -> None:
    dashboard = _fullscreen_overview_dashboard()

    assert dashboard["links"] == [
        {
            "asDropdown": False,
            "icon": "external link",
            "includeVars": False,
            "keepTime": False,
            "tags": [],
            "targetBlank": True,
            "title": "Mission Planner",
            "tooltip": "Open Mission Planner",
            "type": "link",
            "url": "http://localhost:5173/missions",
        }
    ]


def test_fullscreen_overview_clock_defaults_use_large_font_and_required_zones() -> None:
    clock_panels = _clock_panels_by_title()

    assert set(clock_panels) == set(EXPECTED_CLOCK_DEFAULTS)
    for title, timezone in EXPECTED_CLOCK_DEFAULTS.items():
        options = clock_panels[title]["options"]
        assert options["timezone"] == timezone
        assert options["timeSettings"]["fontSize"] == "36px"


def test_fullscreen_overview_keeps_core_map_layers_visible_by_default() -> None:
    layers = _layers_by_name()

    assert CORE_MAP_LAYERS <= layers.keys()
    for layer_name in CORE_MAP_LAYERS:
        assert layers[layer_name].get("opacity", 1) > 0


def test_fullscreen_overview_has_optional_rainviewer_radar_below_operational_layers() -> None:
    layers = _current_position_layers()
    layers_by_name = {layer["name"]: layer for layer in layers}
    radar_layer = layers_by_name[RADAR_LAYER_NAME]

    assert radar_layer["type"] == "xyz"
    assert radar_layer["config"] == {
        "attribution": "Weather radar © Rain Viewer / MeteoLab Inc.",
        "maxZoom": 7,
        "minZoom": 0,
        "url": RAINVIEWER_RADAR_TILE_URL,
    }
    assert radar_layer["opacity"] == 0.7
    assert layers.index(radar_layer) < min(
        layers.index(layers_by_name[layer_name]) for layer_name in CORE_MAP_LAYERS
    )


def test_fullscreen_overview_has_no_hcx_comm_overlay_layer() -> None:
    layers = _current_position_layers()

    layer_names = {layer["name"] for layer in layers}
    for token in HCX_COMM_LAYER_TOKENS:
        assert all(token not in name for name in layer_names)

    layer_sources = {
        Path(layer.get("config", {}).get("src", "")).name
        for layer in layers
        if layer.get("type") == "geojson"
    }
    assert HCX_COMM_LAYER_SOURCES.isdisjoint(layer_sources)


def test_fullscreen_overview_poi_table_hides_active_route_fields() -> None:
    poi_panel = _panel_by_title("POI Quick Reference (Top 5)")
    organize_options = poi_panel["transformations"][0]["options"]

    assert organize_options["excludeByName"]["active"] is True
    assert organize_options["excludeByName"]["is_on_active_route"] is True


def test_fullscreen_overview_live_history_is_split_by_hemisphere_for_idl() -> None:
    map_panel = _panel_by_title("Current Position")
    layers = _layers_by_name()

    west_history = layers["Position History - Western Hemisphere"]
    east_history = layers["Position History - Eastern Hemisphere"]

    assert west_history["type"] == "route"
    assert west_history["filterData"]["options"] == "joinByField-E-F"
    assert west_history["location"] == {
        "latitude": "latitude_history",
        "longitude": "longitude_history",
        "mode": "coords",
    }
    assert east_history["type"] == "route"
    assert east_history["filterData"]["options"] == "joinByField-E_EAST-F_EAST"
    assert east_history["location"] == west_history["location"]

    assert _target_by_ref_id(map_panel, "E")["expr"] == (
        "(starlink_dish_latitude_degrees and starlink_dish_longitude_degrees < 0) "
        "or (starlink_dish_latitude_degrees unless "
        "count_over_time((starlink_dish_longitude_degrees < 0)[$__range:]) > 0)"
    )
    assert _target_by_ref_id(map_panel, "F")["expr"] == (
        "(starlink_dish_longitude_degrees < 0) or "
        "(starlink_dish_longitude_degrees unless "
        "count_over_time((starlink_dish_longitude_degrees < 0)[$__range:]) > 0)"
    )
    assert _target_by_ref_id(map_panel, "E_EAST")["expr"] == (
        "(starlink_dish_latitude_degrees and starlink_dish_longitude_degrees >= 0) "
        "or (starlink_dish_latitude_degrees unless "
        "count_over_time((starlink_dish_longitude_degrees >= 0)[$__range:]) > 0)"
    )
    assert _target_by_ref_id(map_panel, "F_EAST")["expr"] == (
        "(starlink_dish_longitude_degrees >= 0) or "
        "(starlink_dish_longitude_degrees unless "
        "count_over_time((starlink_dish_longitude_degrees >= 0)[$__range:]) > 0)"
    )


def test_fullscreen_overview_poi_table_anchors_eta_left_and_flexes_poi_name() -> None:
    poi_panel = _panel_by_title("POI Quick Reference (Top 5)")
    organize_options = poi_panel["transformations"][0]["options"]

    assert organize_options["indexByName"]["eta_seconds"] == 0
    assert organize_options["indexByName"]["name"] == 1

    poi_overrides = [
        override
        for override in poi_panel["fieldConfig"]["overrides"]
        if override["matcher"] == {"id": "byName", "options": "POI"}
    ]
    eta_override = _field_override_by_name(poi_panel, "ETA")

    assert {"id": "custom.width", "value": 120} in eta_override["properties"]
    assert all(
        property_config["id"] != "custom.width"
        for override in poi_overrides
        for property_config in override["properties"]
    )


def test_fullscreen_overview_gives_map_more_vertical_space() -> None:
    map_panel = _panel_by_title("Current Position")
    packet_loss_panel = _panel_by_title("Packet Loss")

    assert map_panel["gridPos"] == {"h": 23, "w": 18, "x": 0, "y": 3}
    assert packet_loss_panel["gridPos"] == {"h": 4, "w": 18, "x": 0, "y": 26}
