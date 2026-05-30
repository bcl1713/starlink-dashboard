from unittest.mock import MagicMock

import pytest

import main


@pytest.mark.asyncio
async def test_shutdown_event_stops_route_manager_watcher():
    route_manager = MagicMock()
    original_route_manager = main._route_manager
    original_background_task = main._background_task

    try:
        main._route_manager = route_manager
        main._background_task = None

        await main.shutdown_event()

        route_manager.stop_watching.assert_called_once_with()
    finally:
        main._route_manager = original_route_manager
        main._background_task = original_background_task
