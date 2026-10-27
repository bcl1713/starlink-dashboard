"""Routine egress sampling must not invalidate mission export preparation."""

import json
from dataclasses import replace

import pytest

from app.mission.slide_cache.capture import capture_is_current, normalize_capture
from app.services import ground_entry_point as ground
from tests.unit.test_export_preparation import runtime, wait_state


@pytest.fixture
def egress(monkeypatch):
    entry = ground.GroundEntryPoint(
        ip="192.0.2.1",
        city="Test",
        country="US",
        latitude=1,
        longitude=2,
        sampled_at="2026-10-27T07:00:00Z",
        lookup_at="2026-10-27T06:59:00Z",
        provider_geoip=ground.ProviderGeoIP(
            ip="192.0.2.1",
            city="Test",
            country="US",
            latitude=1,
            longitude=2,
            lookup_at="2026-10-27T06:59:00Z",
        ),
    )
    current = [entry]
    monkeypatch.setattr(ground, "get_cached_ground_entry_point", lambda: current[0])
    return current


def test_repeated_egress_sample_during_archive_capture_still_exports(
    tmp_path, monkeypatch, egress
):
    def archive_capture(_):
        egress[0] = replace(egress[0], sampled_at="2026-10-27T07:00:01Z")
        return {
            "schema_version": 1,
            "capture_policy": "sequential_component_snapshots",
            "files": {},
            "components": {},
        }

    with runtime(tmp_path, monkeypatch, archive_capture=archive_capture) as (
        service,
        _,
    ):
        job = service.start("m")
        ready = wait_state(service, job, {"ready", "failed", "superseded"})
        assert ready.state == "ready"
        # A fresh same-IP sample also must not supersede a ready capture or job identity.
        raw = service.capture("m")
        egress[0] = replace(egress[0], sampled_at="2026-10-27T07:00:02Z")
        assert capture_is_current(raw)
        assert service.start("m").id == job.id


def test_capture_pins_egress_sample_evidence_during_normalization(
    tmp_path, monkeypatch, egress
):
    with runtime(tmp_path, monkeypatch) as (service, _):
        raw = service.capture("m")
        original = egress[0].sampled_at
        egress[0] = replace(egress[0], sampled_at="2026-10-27T07:00:01Z")
        _, sources, _, _ = normalize_capture(raw)
        payload = json.loads(
            next(s.content for s in sources if s.name == "ground_entry")
        )
        assert payload["sampled_at"] == original
        assert payload["provider_geoip"]["lookup_at"] == "2026-10-27T06:59:00Z"


@pytest.mark.parametrize(
    "change",
    [
        {"ip": "192.0.2.2"},
        {"latitude": 3},
        {"pop_id": "other"},
        {"freshness": "stale"},
        {"discrepancy": True},
    ],
)
def test_actual_egress_changes_still_invalidate_capture(
    tmp_path, monkeypatch, egress, change
):
    with runtime(tmp_path, monkeypatch) as (service, _):
        raw = service.capture("m")
        egress[0] = replace(egress[0], **change)
        assert not capture_is_current(raw)


def test_refreshed_geoip_times_keep_slide_fingerprint(tmp_path, monkeypatch, egress):
    with runtime(tmp_path, monkeypatch) as (service, _):
        first = normalize_capture(service.capture("m"))[3]["a"][0]
        egress[0] = replace(
            egress[0],
            sampled_at="2026-10-27T07:00:01Z",
            lookup_at="2026-10-27T07:00:01Z",
            provider_geoip=replace(
                egress[0].provider_geoip, lookup_at="2026-10-27T07:00:01Z"
            ),
        )
        second = normalize_capture(service.capture("m"))[3]["a"][0]
        assert first == second


def test_active_lookup_ignores_internal_mission_directories(
    tmp_path, monkeypatch, caplog
):
    import logging

    from app.mission import storage
    from app.services.active_x_link import find_active_mission_leg

    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path)
    for name in (".planning", ".itinerary-imports", ".slide-cache"):
        (tmp_path / name).mkdir()
    with caplog.at_level(logging.WARNING, logger="app.mission.storage"):
        assert find_active_mission_leg() is None
    assert not caplog.records


def test_resampling_during_assembly_keeps_job_ready(tmp_path, monkeypatch, egress):
    import threading

    from app.mission.package.customer_artifacts import build_mission_package_download

    entered, release = threading.Event(), threading.Event()

    def build(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return build_mission_package_download(*args, **kwargs)

    with runtime(tmp_path, monkeypatch, builder=build) as (service, _):
        try:
            job = service.start("m")
            assert entered.wait(2)
            egress[0] = replace(egress[0], sampled_at="2026-10-27T07:00:01Z")
            release.set()
            ready = wait_state(service, job, {"ready", "failed", "superseded"})
            assert ready.state == "ready"
        finally:
            release.set()
