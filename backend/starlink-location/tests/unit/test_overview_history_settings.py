import pytest

from app.services.overview_history_settings import (
    OverviewHistorySettingsStore,
    resolve_overview_history_window_default,
)


def test_persisted_history_window_overrides_the_startup_default_after_restart(
    tmp_path,
):
    settings_path = tmp_path / "overview-history-settings.json"
    initial = OverviewHistorySettingsStore(
        settings_path,
        default_window_seconds=1800,
    )
    assert initial.get_window_seconds() == 1800
    initial.set_window_seconds(900)
    restarted = OverviewHistorySettingsStore(
        settings_path,
        default_window_seconds=1800,
    )
    assert restarted.get_window_seconds() == 900


def test_resolves_the_history_window_from_environment_or_the_thirty_minute_default(
    monkeypatch,
):
    assert resolve_overview_history_window_default() == 1800
    monkeypatch.setenv("STARLINK_HISTORY_WINDOW_SECONDS", "900")
    assert resolve_overview_history_window_default() == 900
    monkeypatch.setenv("STARLINK_HISTORY_WINDOW_SECONDS", "0")
    with pytest.raises(ValueError, match="History window must be positive"):
        resolve_overview_history_window_default()
