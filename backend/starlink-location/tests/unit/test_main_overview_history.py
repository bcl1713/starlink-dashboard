import httpx
import main
from app.api import overview_history
from fastapi.testclient import TestClient


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


def test_lifespan_initializes_and_closes_the_history_runtime(
    monkeypatch,
    tmp_path,
):
    created_clients = []

    class FakeAsyncClient:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs
            self.closed = False
            created_clients.append(self)

        async def get(self, path: str, params: dict) -> httpx.Response:
            assert path == "/api/v1/query_range"
            assert params["start"] == "1781999100"
            assert params["end"] == "1782000000"
            request = httpx.Request(
                "GET",
                f"http://prometheus:9090{path}",
                params=params,
            )
            return httpx.Response(
                200,
                request=request,
                json={
                    "status": "success",
                    "data": {
                        "resultType": "matrix",
                        "result": [],
                    },
                },
            )

        async def aclose(self) -> None:
            self.closed = True

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(
        main,
        "OVERVIEW_HISTORY_SETTINGS_PATH",
        tmp_path / "overview-history.json",
    )
    monkeypatch.setattr(main.time, "time", lambda: 1_782_000_000.0)
    with TestClient(main.app) as client:
        settings_response = client.get("/api/overview-history/settings")
        assert settings_response.status_code == 200
        assert settings_response.json() == {
            "window_seconds": 1800,
        }
        update_response = client.put(
            "/api/overview-history/settings",
            json={
                "window_seconds": 900,
            },
        )
        assert update_response.status_code == 200
        assert update_response.json() == {
            "window_seconds": 900,
        }
        response = client.get("/api/overview-history")
        assert response.status_code == 200
        assert response.json() == {
            "window_seconds": 900,
            "start_timestamp_seconds": 1_781_999_100,
            "end_timestamp_seconds": 1_782_000_000,
            "step_seconds": 1,
            "series": {},
        }
    assert len(created_clients) == 1
    assert created_clients[0].closed is True
    assert main._overview_history_client is None
    assert main._overview_history_settings_store is None


def test_lifespan_exposes_and_cleans_up_clock_settings_store_on_app_state(
    monkeypatch,
    tmp_path,
):
    original_store = main._overview_clock_settings_store
    monkeypatch.setattr(
        main,
        "OVERVIEW_CLOCK_SETTINGS_PATH",
        tmp_path / "overview-clock-settings.json",
    )
    try:
        with TestClient(main.app):
            assert main.app.state.overview_clock_settings_store is (
                main._overview_clock_settings_store
            )
        assert not hasattr(main.app.state, "overview_clock_settings_store")
    finally:
        main._overview_clock_settings_store = original_store
