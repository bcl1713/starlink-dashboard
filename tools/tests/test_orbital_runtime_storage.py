"""The provider clock must remain durable across container recreation."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_orbital_cache_has_durable_independent_writable_storage():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    volumes = compose["services"]["starlink-location"]["volumes"]
    assert "./data/orbital:/app/data/orbital" in volumes
    entrypoint = (ROOT / "backend/starlink-location/entrypoint.sh").read_text()
    assert "/app/data/orbital" in entrypoint
