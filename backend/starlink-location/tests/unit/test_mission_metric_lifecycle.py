"""Exposition-level regression tests for transient mission label ownership."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from app.core.metrics import metric_updater as updater
from app.core.metrics import prometheus_metrics as metrics
from prometheus_client import generate_latest
from prometheus_client.parser import text_string_to_metric_families


def mission_samples():
    return [
        sample
        for family in text_string_to_metric_families(
            generate_latest(metrics.REGISTRY).decode()
        )
        if family.name.startswith("mission_")
        for sample in family.samples
    ]


@pytest.fixture(autouse=True)
def clean_missions():
    for sample in mission_samples():
        updater.clear_mission_metrics(sample.labels["mission_id"])
    yield
    for sample in mission_samples():
        updater.clear_mission_metrics(sample.labels["mission_id"])


def test_deactivation_removes_original_active_child_without_creating_empty_route():
    updater.update_mission_active_metric("A", "route-1")
    updater.update_mission_phase_metric("A", "in_flight")
    updater.update_mission_comm_state_metric("A", "X", 0)
    updater.update_mission_duration_metrics("A", 0, 0)
    updater.update_mission_timeline_timestamp("A", 123)
    updater.update_mission_next_conflict_metric("A", -1)
    assert len(mission_samples()) == 7
    updater.clear_mission_metrics("A")
    updater.clear_mission_metrics("A")
    updater.update_mission_phase_metric("A", "post_arrival")
    assert mission_samples() == []


def test_collector_retains_one_snapshot_and_releases_lock_before_yield():
    updater.update_mission_active_metric("A", "route-1")
    updater.update_mission_phase_metric("A", "in_flight")
    reader = iter(metrics.MISSION_METRICS.collect())
    first = next(reader)
    with ThreadPoolExecutor(max_workers=1) as pool:
        try:
            pool.submit(updater.update_mission_active_metric, "B", "route-2").result(
                timeout=2
            )
            copied = first.samples + [s for family in reader for s in family.samples]
        finally:
            reader.close()
    assert {sample.labels["mission_id"] for sample in copied} == {"A"}
    assert all(sample.value == 1 for sample in copied)


def test_lifecycle_preserves_persistent_aggregates_and_real_zero_values():
    metrics.starlink_network_latency_ms.labels(
        mode="simulation", status="good"
    ).observe(42)
    metrics.starlink_connection_attempts_total.inc()
    before = {
        s.name: s.value
        for f in metrics.REGISTRY.collect()
        for s in f.samples
        if f.name in ("starlink_network_latency_ms", "starlink_connection_attempts")
    }
    updater.update_mission_active_metric("A", "route")
    updater.update_mission_duration_metrics("A", 0, 0)
    assert (
        metrics.REGISTRY.get_sample_value(
            "mission_degraded_seconds", {"mission_id": "A"}
        )
        == 0
    )
    updater.clear_mission_metrics("A")
    after = {
        s.name: s.value
        for f in metrics.REGISTRY.collect()
        for s in f.samples
        if f.name in ("starlink_network_latency_ms", "starlink_connection_attempts")
    }
    assert before == after


def test_switch_rename_reactivate_and_delayed_previous_owner_write():
    for mission, route in [("A", "r1"), ("B", "r2"), ("A", "r1"), ("A", "edited")]:
        updater.update_mission_active_metric(mission, route)
        updater.update_mission_phase_metric(mission, "pre_departure")
        other = "B" if mission == "A" else "A"
        updater.clear_mission_metrics(other)
        updater.update_mission_phase_metric(other, "post_arrival")
        samples = mission_samples()
        assert {s.labels["mission_id"] for s in samples} == {mission}
        active = [s for s in samples if s.name == "mission_active_info"]
        assert [(s.labels["route_id"], s.value) for s in active] == [(route, 1)]


def test_200_transitions_are_bounded_and_collection_is_consistent():
    def mutate():
        for i in range(200):
            mission = f"mission-{i}"
            updater.update_mission_active_metric(mission, f"renamed-{i}")
            updater.update_mission_phase_metric(mission, "in_flight")
            assert len(mission_samples()) <= 2
        updater.clear_mission_metrics("mission-199")

    def scrape():
        for _ in range(200):
            samples = mission_samples()
            assert len({s.labels["mission_id"] for s in samples}) <= 1
            assert all(s.value == 1 for s in samples)

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(mutate), pool.submit(scrape), pool.submit(scrape)]
        for future in futures:
            future.result(timeout=30)
    assert mission_samples() == []
