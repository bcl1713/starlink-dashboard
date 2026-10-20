"""Recording failures cannot prevent live metric publication."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import main


@pytest.mark.parametrize(
    "adapter_config", [Mock(), None, SimpleNamespace(mode="simulation")]
)
def test_recording_failure_keeps_live_metrics(monkeypatch, adapter_config):
    telemetry = Mock()
    runtime = Mock()
    runtime.record_live.side_effect = OSError("disk full")
    monkeypatch.setattr(main.app.state, "flight_event_runtime", runtime, raising=False)
    coordinator = Mock(update=lambda: telemetry)
    coordinator.get_config.return_value = adapter_config
    monkeypatch.setattr(main, "_coordinator", coordinator)
    monkeypatch.setattr(main, "_simulation_config", SimpleNamespace(mode="live"))
    monkeypatch.setattr(main, "_route_manager", Mock())
    monkeypatch.setattr(
        main, "should_automatically_refresh_ground_entry_point", lambda _: False
    )
    monkeypatch.setattr(
        "app.mission.active_context.resolve_active_mission_leg_context",
        lambda _: SimpleNamespace(context=None),
    )
    publish = Mock()
    monkeypatch.setattr("app.core.metrics.update_metrics_from_telemetry", publish)
    main._background_update_tick(Mock(), 1, 1, 0)
    assert publish.call_count == 1
    assert publish.call_args.kwargs["flight_events_managed"] is True
