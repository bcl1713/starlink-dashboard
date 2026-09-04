"""Regression tests for the deployed Mission Planner security policy."""

from pathlib import Path
import re


NGINX = Path(__file__).parents[2] / "frontend/mission-planner/nginx.conf"


def test_mission_planner_csp_allows_only_approved_external_map_tiles() -> None:
    content = NGINX.read_text(encoding="utf-8")
    match = re.search(r'Content-Security-Policy "([^"]+)"', content)
    assert match is not None
    policy = match.group(1)

    assert "img-src 'self' data: https://*.tile.openstreetmap.org https://server.arcgisonline.com" in policy
    assert "rainviewer.com" not in policy
    assert "tilecache" not in policy
    assert "connect-src 'self' ws: wss:" in policy
    assert "object-src 'none'" in policy
    assert "frame-ancestors 'none'" in policy
    assert "form-action 'self'" in policy
    assert "base-uri 'self'" in policy
