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
HCX_COMM_LAYERS = {"CommKaOverlay"}


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


def test_fullscreen_overview_hcx_comm_overlay_is_disabled_but_preserved() -> None:
    layers = _layers_by_name()

    assert HCX_COMM_LAYERS <= layers.keys()
    for layer_name in HCX_COMM_LAYERS:
        layer = layers[layer_name]
        assert layer["type"] == "geojson"
        assert layer["opacity"] == 0
        assert layer["config"]["src"].endswith(
            "/data/sat_coverage/commka.geojson"
        )
        assert layer["config"]["style"].get("opacity", 0) > 0
