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
    "Active X-band Link - Normal",
    "Active X-band Link - Warning",
}
RADAR_LAYER_NAME = "Weather Radar (RainViewer)"
RAINVIEWER_RADAR_TILE_URL = (
    "http://localhost:8000/api/weather/radar/rainviewer/{z}/{x}/{y}.png"
    "?refresh=${__to:date:YYYYMMDDHHmm}"
)
ARCGIS_WORLD_IMAGERY_TILE_URL = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/"
    "World_Imagery/MapServer/tile/{z}/{y}/{x}"
)
ARCGIS_WORLD_IMAGERY_ATTRIBUTION = "Tiles © Esri"
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
        if panel.get("type") == "geomap" and panel.get("title") == "Current Position"
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
    panels = [panel for panel in dashboard["panels"] if panel.get("title") == title]
    assert len(panels) == 1
    return panels[0]


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


def test_fullscreen_overview_uses_keyless_arcgis_world_imagery_basemap() -> None:
    map_panel = _panel_by_title("Current Position")

    assert map_panel["options"]["basemap"] == {
        "config": {
            "attribution": ARCGIS_WORLD_IMAGERY_ATTRIBUTION,
            "url": ARCGIS_WORLD_IMAGERY_TILE_URL,
        },
        "name": "ArcGIS World Imagery",
        "type": "xyz",
    }


def test_fullscreen_overview_current_position_uses_joined_marker_frame() -> None:
    current_position_layers = [
        layer for layer in _current_position_layers() if layer["name"] == "Current Position"
    ]

    assert len(current_position_layers) == 1
    current_position = current_position_layers[0]

    assert current_position["filterData"] == {
        "id": "byRefId",
        "options": "joinByField-A-B-C-D",
    }
    assert "filterByRefId" not in current_position
    assert current_position["location"] == {
        "latitude": "latitude",
        "longitude": "longitude",
        "mode": "coords",
    }
    assert current_position["config"]["style"]["rotation"] == {
        "field": "heading",
        "fixed": 0,
        "max": 360,
        "min": 0,
        "mode": "field",
    }


def test_fullscreen_overview_has_optional_rainviewer_radar_below_operational_layers() -> (
    None
):
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


def test_fullscreen_overview_rainviewer_cache_buster_does_not_use_refresh_variable() -> (
    None
):
    dashboard = _fullscreen_overview_dashboard()
    radar_layer = _layers_by_name()[RADAR_LAYER_NAME]
    variable_names = {variable["name"] for variable in dashboard["templating"]["list"]}

    assert radar_layer["config"]["url"].endswith("?refresh=${__to:date:YYYYMMDDHHmm}")
    assert "radar_refresh" not in variable_names


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


def test_fullscreen_overview_planned_route_layers_use_grafana_v12_ref_filters() -> None:
    layers = _layers_by_name()

    for layer_name, ref_id in (
        ("Planned Route (KML) - Western Hemisphere", "H"),
        ("Planned Route (KML) - Eastern Hemisphere", "H_EAST"),
    ):
        layer = layers[layer_name]
        assert layer["filterData"] == {"id": "byRefId", "options": ref_id}
        assert "filterByRefId" not in layer
        assert layer["location"] == {
            "latitude": "latitude",
            "longitude": "longitude",
            "mode": "coords",
        }
        assert layer["type"] == "route"
        assert layer["config"]["style"]["color"] == {"fixed": "dark-orange"}

    map_panel = _panel_by_title("Current Position")
    targets_by_ref = {target["refId"]: target for target in map_panel["targets"]}
    for ref_id in ("H", "H_EAST"):
        target = targets_by_ref[ref_id]
        assert target["parser"] == "backend"
        assert target["type"] == "json"
        assert target["root_selector"] == "coordinates"


def test_fullscreen_overview_active_x_band_link_uses_split_state_layers() -> None:
    map_panel = _panel_by_title("Current Position")
    layers = _layers_by_name()
    normal_layer = layers["Active X-band Link - Normal"]
    warning_layer = layers["Active X-band Link - Warning"]
    targets_by_ref = {target["refId"]: target for target in map_panel["targets"]}

    assert (
        targets_by_ref["ActiveXLinkNormal"]["url"] == "/api/active-x-link?state=normal"
    )
    assert (
        targets_by_ref["ActiveXLinkWarning"]["url"]
        == "/api/active-x-link?state=warning"
    )
    assert targets_by_ref["ActiveXLinkNormal"]["root_selector"] == "coordinates"
    assert targets_by_ref["ActiveXLinkWarning"]["root_selector"] == "coordinates"

    assert normal_layer["type"] == "route"
    assert warning_layer["type"] == "route"
    assert normal_layer["filterData"] == {
        "id": "byRefId",
        "options": "ActiveXLinkNormal",
    }
    assert warning_layer["filterData"] == {
        "id": "byRefId",
        "options": "ActiveXLinkWarning",
    }
    assert normal_layer["config"]["style"]["color"] == {"fixed": "green"}
    assert warning_layer["config"]["style"]["color"] == {"fixed": "yellow"}
    assert normal_layer["location"] == {
        "latitude": "latitude",
        "longitude": "longitude",
        "mode": "coords",
    }
    assert warning_layer["location"] == normal_layer["location"]


def test_fullscreen_overview_poi_table_hides_active_route_fields() -> None:
    poi_panel = _panel_by_title("POI Quick Reference (Top 5)")
    organize_options = poi_panel["transformations"][0]["options"]

    assert organize_options["excludeByName"]["active"] is True
    assert organize_options["excludeByName"]["is_on_active_route"] is True


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
    assert packet_loss_panel["gridPos"] == {"h": 4, "w": 7, "x": 11, "y": 26}


def test_fullscreen_overview_places_obstruction_gauge_between_ground_entry_point_and_packet_loss() -> (
    None
):
    ground_entry_panel = _panel_by_title("Ground Entry Point")
    obstruction_panel = _panel_by_title("Obstruction %")
    packet_loss_panel = _panel_by_title("Packet Loss")
    layers_by_name = _layers_by_name()

    assert ground_entry_panel["gridPos"] == {"h": 4, "w": 7, "x": 0, "y": 26}
    assert obstruction_panel["gridPos"] == {"h": 4, "w": 4, "x": 7, "y": 26}
    assert packet_loss_panel["gridPos"] == {"h": 4, "w": 7, "x": 11, "y": 26}
    assert "Ground Entry Point" in layers_by_name
    assert (
        layers_by_name["Ground Entry Point"]["config"]["coords"]["lat"]
        == "starlink_ground_entry_point_latitude_degrees"
    )
    assert (
        layers_by_name["Ground Entry Point"]["config"]["coords"]["lon"]
        == "starlink_ground_entry_point_longitude_degrees"
    )


def test_fullscreen_overview_ground_entry_point_uses_safe_display_label() -> None:
    ground_entry_panel = _panel_by_title("Ground Entry Point")

    assert ground_entry_panel["targets"] == [
        {
            "datasource": {
                "type": "prometheus",
                "uid": "PBFA97CFB590B2093",
            },
            "expr": "starlink_ground_entry_point_info",
            "instant": True,
            "legendFormat": "{{display}}",
            "refId": "A",
        }
    ]


def test_fullscreen_overview_obstruction_gauge_uses_absolute_thresholds() -> None:
    obstruction_panel = _panel_by_title("Obstruction %")
    defaults = obstruction_panel["fieldConfig"]["defaults"]

    assert obstruction_panel["type"] == "gauge"
    assert defaults["min"] == 0
    assert defaults["max"] == 20
    assert defaults["unit"] == "percent"
    assert defaults["thresholds"] == {
        "mode": "absolute",
        "steps": [
            {"color": "green", "value": 0},
            {"color": "yellow", "value": 5},
            {"color": "red", "value": 10},
        ],
    }
    assert obstruction_panel["targets"] == [
        {
            "expr": "starlink_dish_obstruction_percent",
            "interval": "1s",
            "intervalFactor": 1,
            "legendFormat": "Obstruction",
            "refId": "A",
        }
    ]
