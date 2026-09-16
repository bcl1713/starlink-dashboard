import httpx

import main
from app.api import overview_history


def test_initializes_the_history_reader_with_a_persistent_window_store(
    monkeypatch,
    tmp_path,
):
    created_clients = []

    class FakeAsyncClient:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs
            created_clients.append(self)

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(
        main,
        "OVERVIEW_HISTORY_SETTINGS_PATH",
        tmp_path / "overview-history.json",
    )
    original_client = main._overview_history_client
    original_settings_store = main._overview_history_settings_store
    overview_history.set_overview_history_reader(None)
    try:
        main.initialize_overview_history_runtime()
        assert len(created_clients) == 1
        assert created_clients[0].kwargs["base_url"] == "http://prometheus:9090"
        assert main._overview_history_settings_store.get_window_seconds() == 1800
        assert overview_history._overview_history_reader is not None
    finally:
        overview_history.set_overview_history_reader(None)
        main._overview_history_client = original_client
        main._overview_history_settings_store = original_settings_store
