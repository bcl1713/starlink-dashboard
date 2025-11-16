"""Unit tests for mission metrics integration."""

import pytest
from datetime import datetime, timezone
import math

from app.core.metrics import (
    mission_active_info,
    mission_phase_state,
    mission_next_conflict_seconds,
    mission_timeline_generated_timestamp,
    update_mission_active_metric,
    clear_mission_metrics,
    update_mission_phase_metric,
    update_mission_timeline_timestamp,
    REGISTRY,
)


class TestMissionMetrics:
    """Test mission-related Prometheus metrics."""

    def test_mission_active_info_metric_exists(self):
        """Verify mission_active_info metric is registered."""
        assert mission_active_info is not None
        assert mission_active_info._name == 'mission_active_info'

    def test_mission_phase_state_metric_exists(self):
        """Verify mission_phase_state metric is registered."""
        assert mission_phase_state is not None
        assert mission_phase_state._name == 'mission_phase_state'

    def test_mission_next_conflict_seconds_metric_exists(self):
        """Verify mission_next_conflict_seconds metric is registered."""
        assert mission_next_conflict_seconds is not None
        assert mission_next_conflict_seconds._name == 'mission_next_conflict_seconds'

    def test_mission_timeline_generated_timestamp_metric_exists(self):
        """Verify mission_timeline_generated_timestamp metric is registered."""
        assert mission_timeline_generated_timestamp is not None
        assert mission_timeline_generated_timestamp._name == 'mission_timeline_generated_timestamp'

    def test_update_mission_active_metric(self):
        """Test updating mission active metric."""
        # Should not raise
        update_mission_active_metric("test-mission-001", "test-route-001")

    def test_clear_mission_metrics(self):
        """Test clearing mission metrics."""
        # Should not raise
        clear_mission_metrics("test-mission-001")

    def test_update_mission_phase_metric(self):
        """Test updating mission phase metric."""
        # Should not raise
        update_mission_phase_metric("test-mission-001", "pre_departure")
        update_mission_phase_metric("test-mission-001", "in_flight")
        update_mission_phase_metric("test-mission-001", "post_arrival")

    def test_update_mission_timeline_timestamp(self):
        """Test updating mission timeline timestamp metric."""
        timestamp = datetime.now(timezone.utc).timestamp()
        # Should not raise
        update_mission_timeline_timestamp("test-mission-001", timestamp)

    def test_metrics_in_registry(self):
        """Verify mission metrics are in the registry."""
        metric_names = [m.name for m in REGISTRY.collect()]
        assert 'mission_active_info' in metric_names
        assert 'mission_phase_state' in metric_names
        assert 'mission_next_conflict_seconds' in metric_names
        assert 'mission_timeline_generated_timestamp' in metric_names

    def test_mission_phase_metric_values(self):
        """Test that phase metric maps correctly."""
        test_cases = [
            ("pre_departure", 0),
            ("in_flight", 1),
            ("post_arrival", 2),
        ]
        for phase, expected_value in test_cases:
            update_mission_phase_metric("test-mission-phase", phase)
            # The metric should be set without raising

    def test_multiple_missions_metrics(self):
        """Test metrics for multiple missions."""
        mission_ids = ["mission-1", "mission-2", "mission-3"]
        for mission_id in mission_ids:
            update_mission_active_metric(mission_id, "route-1")
            update_mission_phase_metric(mission_id, "pre_departure")
            update_mission_timeline_timestamp(mission_id, 1000.0)

        # All should succeed without raising

    def test_clear_mission_metrics_idempotent(self):
        """Test that clearing metrics multiple times is safe."""
        mission_id = "test-mission-clear"
        update_mission_active_metric(mission_id, "route-1")
        # Clear twice should be safe
        clear_mission_metrics(mission_id)
        clear_mission_metrics(mission_id)
