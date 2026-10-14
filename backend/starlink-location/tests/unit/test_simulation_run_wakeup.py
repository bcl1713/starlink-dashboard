"""Replay activation interrupts an already pending ordinary collector sleep."""

import asyncio
from types import SimpleNamespace

import pytest

from app.simulation.run_wakeup import ReplayWakeup


@pytest.mark.asyncio
async def test_activation_wakes_the_actual_background_loop(monkeypatch):
    import main

    wakeup = ReplayWakeup()
    observed = []
    state = {"running": False}
    collected, ordinary = asyncio.Event(), asyncio.Event()
    loop = asyncio.get_running_loop()

    def update():
        observed.append("ordinary")
        loop.call_soon_threadsafe(ordinary.set)

    def collect(*args):
        observed.append("replay")
        loop.call_soon_threadsafe(collected.set)

    service = SimpleNamespace(
        wakeup=wakeup,
        runtime=SimpleNamespace(
            selected_plan=lambda: object() if state["running"] else None,
            seconds_until_next_tick=lambda: 1,
        ),
        status=lambda: SimpleNamespace(state="running" if state["running"] else "idle"),
        collect=collect,
    )
    monkeypatch.setattr(
        main.app.state, "simulation_run_service", service, raising=False
    )
    monkeypatch.setattr(main, "_coordinator", SimpleNamespace(update=update))
    monkeypatch.setattr(
        main,
        "_simulation_config",
        SimpleNamespace(mode="simulation", update_interval_seconds=30),
    )
    task = asyncio.create_task(main._background_update_loop())
    try:
        await asyncio.wait_for(ordinary.wait(), 0.5)
        assert observed == ["ordinary"]
        state["running"] = True
        wakeup.wake()
        await asyncio.wait_for(collected.wait(), 0.5)
        assert observed == ["ordinary", "replay"]
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
