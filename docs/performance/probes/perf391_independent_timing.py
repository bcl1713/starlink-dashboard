"""Bounded HTTP boundary diagnostic with explicit fault injection and cleanup."""

import json
import os
import time
from pathlib import Path


async def http_timing(root, output, main, manager, coordinator):
    """Short mechanism discrimination; injected stalls are not historical causes."""
    import asyncio
    import importlib.util
    import socket

    import uvicorn
    from app.core.metrics import prometheus_metrics as metrics
    from app.core.metrics.lifecycle import MetricsRefreshOwner
    from app.mission.storage import get_active_leg_lock
    from fastapi import FastAPI, Request

    path = root / "tools/acceptance/performance_availability/state.py"
    spec = importlib.util.spec_from_file_location("independent_state", path)
    state = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(state)
    rows = []

    def record(kind, **fields):
        rows.append(dict(kind=kind, at=time.time(), mono=time.monotonic(), **fields))

    api = FastAPI()

    @api.middleware("http")
    async def boundary(request: Request, call_next):
        record("asgi_arrival", request=request.headers.get("x-diagnostic-id"))
        result = await call_next(request)
        record("asgi_response", request=request.headers.get("x-diagnostic-id"))
        return result

    @api.get("/api/_acceptance/availability/state")
    def capture(request: Request):
        ident = request.headers.get("x-diagnostic-id")
        entered = time.monotonic()
        record("worker_enter", request=ident)
        with get_active_leg_lock():
            record(
                "admitted", request=ident, wait_ms=(time.monotonic() - entered) * 1000
            )
            result = state.capture(main, metrics)
            result["diagnostic_acquired_at"] = (
                coordinator.get_current_telemetry().timestamp.timestamp()
            )
        return result

    original_update = coordinator.update

    def update(*args, **kwargs):
        record("source_enter")
        result = original_update(*args, **kwargs)
        record("source_exit", acquired_at=result.timestamp.timestamp())
        return result

    coordinator.update = update
    original_tick = main._background_update_tick

    def tick(*args, **kwargs):
        record("tick_enter")
        try:
            return original_tick(*args, **kwargs)
        finally:
            record("tick_exit")

    main._background_update_tick = tick
    refresh_count = 0
    original_refresh = main._refresh_metrics_without_collection

    def refresh():
        nonlocal refresh_count
        refresh_count += 1
        return original_refresh()

    owner = MetricsRefreshOwner(refresh, background_enabled=True)
    from app.services.flight_state import get_flight_state_manager

    owner.attach(coordinator, manager, main._route_manager, get_flight_state_manager())
    main.app.state.metrics_refresh_owner = owner
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    listener.setblocking(False)
    port = listener.getsockname()[1]
    (output / "timing-listener.json").write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "pgid": os.getpgid(0),
                "port": port,
                "owner": "perf391-independent",
                "purpose": "36-second diagnostic",
                "stop": "SIGTERM owner PID",
            }
        )
    )
    server = uvicorn.Server(uvicorn.Config(api, log_level="error", lifespan="off"))
    serving = asyncio.create_task(server.serve(sockets=[listener]))
    producer = asyncio.create_task(main._background_update_loop(manager))
    lag = []

    async def heartbeat():
        deadline = time.monotonic()
        while True:
            deadline += 0.02
            await asyncio.sleep(max(0, deadline - time.monotonic()))
            lag.append(
                {
                    "at": time.time(),
                    "delay_ms": max(0, time.monotonic() - deadline) * 1000,
                }
            )

    beating = asyncio.create_task(heartbeat())
    while not server.started:
        await asyncio.sleep(0.01)
    script = Path(__file__).with_name("perf391_independent_observer.mjs")
    observer = await asyncio.create_subprocess_exec(
        "node",
        str(script),
        str(port),
        str(output),
        str(root / "tools/acceptance/performance_availability/monitor.mjs"),
    )
    (output / "timing-observer-owner.json").write_text(
        json.dumps({"pid": observer.pid, "parent": os.getpid()})
    )

    async def admission_stall():
        await asyncio.sleep(9.8)

        def hold():
            with get_active_leg_lock():
                record("injected_admission_start")
                time.sleep(0.8)
                record("injected_admission_end")

        await asyncio.to_thread(hold)

    async def event_loop_stall():
        await asyncio.sleep(19.8)
        record("injected_backend_loop_start")
        time.sleep(0.8)  # noqa: ASYNC251 - deliberate backend loop fault injection
        record("injected_backend_loop_end")

    stalls = [
        asyncio.create_task(admission_stall()),
        asyncio.create_task(event_loop_stall()),
    ]
    try:
        await asyncio.wait_for(observer.wait(), timeout=45)
        if observer.returncode:
            raise RuntimeError(f"Observer failed: {observer.returncode}")
    finally:
        if observer.returncode is None:
            observer.terminate()
            try:
                await asyncio.wait_for(observer.wait(), 3)
            except TimeoutError:
                observer.kill()
                await observer.wait()
        for task in stalls + [producer, beating]:
            task.cancel()
        await asyncio.gather(*stalls, producer, beating, return_exceptions=True)
        await owner.close()
        server.should_exit = True
        await serving
        listener.close()
        await asyncio.get_running_loop().shutdown_default_executor()
    return {
        "events": rows,
        "event_loop": lag,
        "derived_refreshes": refresh_count,
        "observer": json.loads((output / "observer.json").read_text()),
        "owned_listener_closed": listener.fileno() == -1,
        "observer_exitcode": observer.returncode,
    }
