"""Scientific runtime is opt-in, bounded and never mounted writable by API."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_worker_profile_has_aggregate_cpu_memory_limit_and_no_public_port():
    overlay = yaml.safe_load((ROOT / "docker-compose.gfs.yml").read_text())
    worker = overlay["services"]["gfs-worker"]
    assert worker["profiles"] == ["gfs"]
    assert worker["cpus"] == 1.0
    assert worker["mem_limit"] == "1g"
    assert "ports" not in worker
    assert worker["user"] == "1000:1000"
    assert "./data/settings:/app/data/settings:ro" in worker["volumes"]
    api = overlay["services"]["starlink-location"]
    assert "gfs_products:/app/data/gfs:ro" in api["volumes"]
    assert "gfs_mailbox:/app/data/gfs-mailbox" in api["volumes"]


def test_scientific_dependencies_are_separate_from_core_image():
    api = (ROOT / "backend/starlink-location/Dockerfile").read_text()
    worker = (ROOT / "backend/starlink-location/Dockerfile.gfs").read_text()
    assert "requirements-gfs" not in api
    assert "requirements-gfs.txt" in worker
    assert "ACCEPTANCE_CANDIDATE_SHA" in worker
    assert "1000" in worker
    assert "OPENBLAS_NUM_THREADS=1" in worker


def test_every_production_candidate_image_has_a_revision_label():
    for name in (
        "backend/starlink-location/Dockerfile",
        "backend/starlink-location/Dockerfile.gfs",
        "frontend/mission-planner/Dockerfile",
    ):
        runtime = (ROOT / name).read_text().rsplit("FROM ", 1)[1]
        assert "ARG ACCEPTANCE_CANDIDATE_SHA" in runtime
        assert "LABEL org.opencontainers.image.revision=$ACCEPTANCE_CANDIDATE_SHA" in runtime
