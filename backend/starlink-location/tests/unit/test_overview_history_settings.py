from app.services.overview_history_settings import OverviewHistorySettingsStore


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
