"""Mission Planner nginx security header tests."""

from __future__ import annotations

import re
from pathlib import Path

NGINX_CONF = Path(__file__).resolve().parents[2] / "frontend/mission-planner/nginx.conf"


def _nginx_locations() -> list[tuple[str, str]]:
    config = NGINX_CONF.read_text(encoding="utf-8")
    return [
        (modifier or "", pattern)
        for modifier, pattern in re.findall(
            r"location\s+(?:(=|\^~|~\*)\s+)?([^{\s]+)\s*\{", config
        )
    ]


def _selected_location(uri: str) -> tuple[str, str] | None:
    locations = _nginx_locations()
    for modifier, pattern in locations:
        if modifier == "=" and uri == pattern:
            return modifier, pattern

    prefix = max(
        (
            (modifier, pattern)
            for modifier, pattern in locations
            if modifier in {"", "^~"} and uri.startswith(pattern)
        ),
        key=lambda item: len(item[1]),
        default=None,
    )
    if prefix is not None and prefix[0] == "^~":
        return prefix

    for modifier, pattern in locations:
        if modifier == "~*" and re.search(pattern, uri, flags=re.IGNORECASE):
            return modifier, pattern
    return prefix


def _csp_directives() -> dict[str, set[str]]:
    config = NGINX_CONF.read_text(encoding="utf-8")
    match = re.search(r'Content-Security-Policy\s+"([^"]+)"', config)
    assert match is not None
    directives: dict[str, set[str]] = {}
    for directive in match.group(1).split(";"):
        tokens = directive.strip().split()
        if tokens:
            directives[tokens[0]] = set(tokens[1:])
    return directives


def test_mission_planner_csp_has_exact_weather_proxy_boundaries() -> None:
    directives = _csp_directives()

    assert directives["img-src"] == {
        "'self'",
        "data:",
        "blob:",
        "https://*.tile.openstreetmap.org",
        "https://server.arcgisonline.com",
    }
    assert directives["connect-src"] == {"'self'", "ws:", "wss:"}

    serialized_tokens = set().union(*directives.values())
    assert "https:" not in serialized_tokens
    assert "https://api.rainviewer.com" not in serialized_tokens
    assert "https://tilecache.rainviewer.com" not in serialized_tokens
    assert "http://localhost:9090" not in serialized_tokens
    assert "http://localhost:3000" not in serialized_tokens
    assert all(
        token.count("*") == 0 or token == "https://*.tile.openstreetmap.org"
        for token in serialized_tokens
    )


def test_mission_planner_nginx_routes_api_png_before_static_regex() -> None:
    assert _selected_location("/api/weather/radar/rainviewer/3/4/5.png") == (
        "^~",
        "/api/",
    )
    assert _selected_location("/assets/radar-preview.png") == (
        "~*",
        r"\.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$",
    )
    assert _selected_location("/api/v2/missions/import") == (
        "=",
        "/api/v2/missions/import",
    )
