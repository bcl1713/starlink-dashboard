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
HCX_COMM_LAYER_TOKENS = {"CommKaOverlay", "HCX"}
HCX_COMM_LAYER_SOURCES = {"commka.geojson"}


def _fullscreen_overview_dashboard() -> dict:
    return json.loads(DASHBOARD_PATH.read_text())


def _current_position_panel() -> dict:
    dashboard = _fullscreen_overview_dashboard()
    geomap_panels = [
        panel
        for panel in dashboard["panels"]
        if panel.get("type") == "geomap"
        and panel.get("title") == "Current Position"
    ]
    assert len(geomap_panels) == 1
    return geomap_panels[0]


def _current_position_layers() -> list[dict]:
    return _current_position_panel()["options"]["layers"]


def _layers_by_name() -> dict[str, dict]:
    return {layer["name"]: layer for layer in _current_position_layers()}


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


def test_fullscreen_overview_keeps_core_map_layers_visible_by_default() -> None:
    layers = _layers_by_name()

    assert CORE_MAP_LAYERS <= layers.keys()
    for layer_name in CORE_MAP_LAYERS:
        assert layers[layer_name].get("opacity", 1) > 0


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


def test_fullscreen_overview_refits_view_to_current_position_on_data_refresh() -> None:
    panel = _current_position_panel()
    view = panel["options"]["view"]

    assert view["id"] == "fit"
    assert view["allLayers"] is False
    assert view["layer"] == "Current Position"
    assert view["lastOnly"] is True
    assert view["zoom"] == 6
    assert view["padding"] == 25


def test_fullscreen_overview_documents_grafana_follow_limitation() -> None:
    panel = _current_position_panel()
    description = panel["description"]
    dashboard_docs = (REPO_ROOT / "docs" / "grafana-dashboards.md").read_text()

    assert "Grafana Geomap does not support true continuous auto-follow" in description
    assert "refits to the latest Current Position" in description
    assert "true continuous auto-follow" in dashboard_docs
    assert "Fit to data" in dashboard_docs
