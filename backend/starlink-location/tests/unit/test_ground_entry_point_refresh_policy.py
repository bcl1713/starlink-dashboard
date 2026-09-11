import asyncio

import main
import pytest

"""Tests for automatic ground-entry discovery by operating mode."""

from app.models.config import SimulationConfig


def test_simulation_does_not_automatically_refresh_ground_entry_point() -> None:
    assert (
        main.should_automatically_refresh_ground_entry_point(
            SimulationConfig(mode="simulation")
        )
        is False
    )


def test_live_mode_automatically_refreshes_ground_entry_point() -> None:
    assert (
        main.should_automatically_refresh_ground_entry_point(
            SimulationConfig(mode="live")
        )
        is True
    )


class SingleUpdateCoordinator:
    def __init__(self) -> None:
        self.update_calls = 0

    def update(self):
        self.update_calls += 1


@pytest.mark.asyncio
async def test_simulation_background_update_skips_gep_refresh(
    monkeypatch,
) -> None:
    coordinator = SingleUpdateCoordinator()
    refresh_calls: list[float] = []

    def record_refresh(*, refresh_interval_seconds: float) -> None:
        refresh_calls.append(refresh_interval_seconds)

    async def cancel_after_first_update(_: float) -> None:
        raise asyncio.CancelledError

    monkeypatch.setattr(main, "_simulation_config", SimulationConfig(mode="simulation"))
    monkeypatch.setattr(main, "_coordinator", coordinator)
    monkeypatch.setattr(
        main,
        "maybe_refresh_ground_entry_point_metrics",
        record_refresh,
    )
    monkeypatch.setattr(main.asyncio, "sleep", cancel_after_first_update)

    with pytest.raises(asyncio.CancelledError):
        await main._background_update_loop()

    assert refresh_calls == []
    assert coordinator.update_calls == 1


@pytest.mark.asyncio
async def test_live_background_update_refreshes_gep_before_telemetry(
    monkeypatch,
) -> None:
    coordinator = SingleUpdateCoordinator()
    refresh_calls: list[float] = []

    def record_refresh(*, refresh_interval_seconds: float) -> None:
        refresh_calls.append(refresh_interval_seconds)

    async def cancel_after_first_update(_: float) -> None:
        raise asyncio.CancelledError

    monkeypatch.setattr(main, "_simulation_config", SimulationConfig(mode="live"))
    monkeypatch.setattr(main, "_coordinator", coordinator)
    monkeypatch.setattr(
        main,
        "maybe_refresh_ground_entry_point_metrics",
        record_refresh,
    )
    monkeypatch.setattr(main.asyncio, "sleep", cancel_after_first_update)

    with pytest.raises(asyncio.CancelledError):
        await main._background_update_loop()

    assert refresh_calls == [1.0]
    assert coordinator.update_calls == 1
