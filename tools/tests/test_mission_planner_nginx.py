"""Mission Planner nginx security header tests."""

from __future__ import annotations

import re
from pathlib import Path

NGINX_CONF = Path(__file__).resolve().parents[2] / "frontend/mission-planner/nginx.conf"


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
