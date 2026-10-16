"""Real disposable children exercise pipe limits, cancellation and owner leases."""

import asyncio
import importlib
import os
import signal
import sys
import time
from pathlib import Path

import pytest

from app.models.route_sigmets import RouteContext
from app.services.overview_weather.protocol import WeatherUnavailable


def decoder():
    name = "app.services.aviation_weather.route_decode"
    assert importlib.util.find_spec(name), "bounded worker owner implementation missing"
    return importlib.import_module(name)


def context(identity="0"):
    return RouteContext(
        context_key=identity * 64,
        source="ordinary",
        route_id="route",
        route_name="Route",
        runtime_id=None,
        run_id=None,
        points=[[-2, 0], [2, 0]],
    )


COLLECTION = {
    "type": "FeatureCollection",
    "features": [
        {
            "id": "sigmet",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[-1, -1], [1, -1], [1, 1], [-1, 1], [-1, -1]]],
            },
        }
    ],
}


@pytest.fixture
async def children(monkeypatch, tmp_path):
    original = asyncio.create_subprocess_exec
    owned = []
    ownership = Path(
        os.environ.get(
            "TASK_ROUTE_SIGMETS_RESOURCE_LOG", str(tmp_path / "owned-processes.log")
        )
    )

    def record(message):
        with ownership.open("a") as output:
            output.write(message + "\n")

    async def launch(*args, **kwargs):
        assert all(
            p.returncode is not None for p in owned
        ), "overlapping worker processes"
        await asyncio.to_thread(
            record,
            f"starting worker command={args!r} owned by pytest pid={os.getpid()}",
        )
        process = await original(*args, **kwargs)
        owned.append(process)
        await asyncio.to_thread(
            record, f"pid={process.pid} pgid={process.pid} command={args!r}"
        )
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", launch)
    yield owned
    # The implementation must finish its cleanup before returning to its caller.
    for process in owned:
        reaped = process.returncode is not None
        if not reaped:
            if os.getpgid(process.pid) == process.pid:
                os.killpg(process.pid, signal.SIGKILL)
            async with asyncio.timeout(3):
                await process.stdout.read()
                await process.wait()
        assert reaped, "worker owner leaked a process; test cleanup killed/reaped it"
        with pytest.raises(ProcessLookupError):
            os.kill(process.pid, 0)
        assert process.stdin.is_closing()
        assert process.stdout.at_eof()
        await asyncio.to_thread(
            record, f"verified reaped pid={process.pid} pgid={process.pid} pipes closed"
        )


async def test_real_worker_returns_geometry(children):
    result = await decoder().evaluate_in_worker(context(), COLLECTION)
    assert result.matches[0].feature_id == "sigmet"
    assert len(children) == 1


@pytest.mark.parametrize(
    "program",
    [
        "import time; time.sleep(60)",
        "import time,signal; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(60)",
        "import os; os.write(1, b'x' * (9 * 1024**2))",
        "print('not json')",
    ],
)
async def test_hung_excessive_and_invalid_workers_are_unavailable(
    program, children, monkeypatch
):
    module = decoder()
    monkeypatch.setattr(module, "WORKER_COMMAND", (sys.executable, "-c", program))
    start = time.monotonic()
    with pytest.raises(WeatherUnavailable):
        await module.evaluate_in_worker(context(), COLLECTION)
    assert time.monotonic() - start < 6.25


async def test_repeated_cancellation_reaps_term_ignoring_child(
    children, monkeypatch, tmp_path
):
    module = decoder()
    ready = tmp_path / "ready"
    program = f"import signal,time,pathlib; signal.signal(signal.SIGTERM, signal.SIG_IGN); pathlib.Path({str(ready)!r}).touch(); time.sleep(60)"
    monkeypatch.setattr(module, "WORKER_COMMAND", (sys.executable, "-c", program))
    task = asyncio.create_task(module.evaluate_in_worker(context(), COLLECTION))
    try:
        async with asyncio.timeout(3):
            while not ready.exists():
                await asyncio.sleep(0.01)
        start = time.monotonic()
        task.cancel()
        await asyncio.sleep(0.05)
        task.cancel()
        await asyncio.sleep(0.05)
        assert not task.done()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert time.monotonic() - start < 1.25
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_shared_readers_and_supersession_have_one_worker(children, monkeypatch):
    module = decoder()
    owner = module.GeometryWorker()
    program = 'import sys,time; sys.stdin.buffer.read(); time.sleep(.15); print(\'{"matches":[],"unresolved":[],"complete":true,"reason":null}\')'
    monkeypatch.setattr(module, "WORKER_COMMAND", (sys.executable, "-c", program))
    first = asyncio.create_task(owner.evaluate(context(), COLLECTION))
    twin = asyncio.create_task(owner.evaluate(context(), COLLECTION))
    tasks = [first, twin]
    try:
        await asyncio.sleep(0.05)
        first.cancel()
        await asyncio.gather(first, return_exceptions=True)
        assert not twin.done()
        assert (await twin).complete
        assert len(children) == 1
        old = asyncio.create_task(owner.evaluate(context("1"), COLLECTION))
        tasks.append(old)
        await asyncio.sleep(0.03)
        for key in "23456789":
            tasks.append(asyncio.create_task(owner.evaluate(context(key), COLLECTION)))
        assert (await tasks[-1]).complete
        await asyncio.gather(*tasks, return_exceptions=True)
        assert len(children) <= 3  # joined request, superseded worker, latest pending
    finally:
        await owner.aclose()
        await asyncio.gather(*tasks, return_exceptions=True)


async def test_input_and_output_contract_caps(children):
    module = decoder()
    with pytest.raises(WeatherUnavailable):
        await module.evaluate_in_worker(
            context(), {"features": [], "padding": "x" * (module.MAX_INPUT_BYTES + 1)}
        )
    assert children == []
    bad = {"features": [{"id": str(i), "geometry": None} for i in range(501)]}
    with pytest.raises(WeatherUnavailable):
        await module.evaluate_in_worker(context(), bad)


async def test_worker_rejects_vertex_limit_and_output_contract(children, monkeypatch):
    module = decoder()
    # Use the actual entrypoint: malformed geometry must become unavailable.
    with pytest.raises(WeatherUnavailable):
        await module.evaluate_in_worker(
            context(),
            {
                "features": [
                    {
                        "id": "bad",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[0, 0]] * 100001],
                        },
                    }
                ]
            },
        )
    monkeypatch.setattr(
        module,
        "WORKER_COMMAND",
        (
            sys.executable,
            "-c",
            'print(\'{"matches":[],"unresolved":[],"complete":true,"reason":null,"unexpected":1}\')',
        ),
    )
    with pytest.raises(WeatherUnavailable):
        await module.evaluate_in_worker(context(), COLLECTION)


async def test_cancellation_during_creation_is_reaped(children, monkeypatch):
    module = decoder()
    original = asyncio.create_subprocess_exec
    spawned, release = asyncio.Event(), asyncio.Event()

    async def delayed(*args, **kwargs):
        process = await original(*args, **kwargs)
        spawned.set()
        await release.wait()
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", delayed)
    monkeypatch.setattr(
        module, "WORKER_COMMAND", (sys.executable, "-c", "import time; time.sleep(60)")
    )
    task = asyncio.create_task(module.evaluate_in_worker(context(), COLLECTION))
    try:
        await spawned.wait()
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        release.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_last_lease_and_shutdown_reap_owner(children, monkeypatch):
    module = decoder()
    monkeypatch.setattr(
        module, "WORKER_COMMAND", (sys.executable, "-c", "import time; time.sleep(60)")
    )
    owner = module.GeometryWorker()
    task = asyncio.create_task(owner.evaluate(context(), COLLECTION))
    try:
        async with asyncio.timeout(3):
            while not children:
                await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert children[0].returncode is not None
        task = asyncio.create_task(owner.evaluate(context("1"), COLLECTION))
        async with asyncio.timeout(3):
            while len(children) < 2:
                await asyncio.sleep(0.01)
        await owner.aclose()
        with pytest.raises(WeatherUnavailable):
            await task
        with pytest.raises(WeatherUnavailable):
            await owner.evaluate(context(), COLLECTION)
    finally:
        await owner.aclose()
        await asyncio.gather(task, return_exceptions=True)


async def test_superseded_pending_inputs_are_not_serialized(children, monkeypatch):
    module = decoder()
    original = module._encode
    encoded = []

    def slow_encode(ctx, collection):
        encoded.append(ctx.context_key)
        time.sleep(0.1)
        return original(ctx, collection)

    monkeypatch.setattr(module, "_encode", slow_encode)
    owner = module.GeometryWorker()
    tasks = [
        asyncio.create_task(owner.evaluate(context(key), COLLECTION))
        for key in "0123456789"
    ]
    try:
        assert (await tasks[-1]).matches
        results = await asyncio.gather(*tasks, return_exceptions=True)
        assert all(isinstance(result, WeatherUnavailable) for result in results[:-1])
        assert len(encoded) <= 2
    finally:
        await owner.aclose()
        await asyncio.gather(*tasks, return_exceptions=True)


async def test_stdout_flood_ignoring_term_is_reaped_within_grace(children, monkeypatch):
    module = decoder()
    program = "import os,signal; signal.signal(signal.SIGTERM, signal.SIG_IGN)\nwhile True: os.write(1, b'x' * 65536)"
    monkeypatch.setattr(module, "WORKER_COMMAND", (sys.executable, "-c", program))
    started = time.monotonic()
    with pytest.raises(WeatherUnavailable):
        await module.evaluate_in_worker(context(), COLLECTION)
    assert time.monotonic() - started < 1.5


async def test_actual_entrypoint_sets_cpu_memory_affinity_and_thread_caps(
    children, monkeypatch
):
    module = decoder()
    program = """
import json, os, resource, runpy, sys
class Output:
    def write(self, data):
        result = json.loads(data)
        result["reason"] = json.dumps({
            "cpu": resource.getrlimit(resource.RLIMIT_CPU),
            "ram": resource.getrlimit(resource.RLIMIT_AS),
            "affinity": len(os.sched_getaffinity(0)),
            "threads": [os.environ["OPENBLAS_NUM_THREADS"], os.environ["OMP_NUM_THREADS"]],
        })
        sys.__stdout__.buffer.write(json.dumps(result).encode())
class Stream:
    buffer = Output()
sys.stdout = Stream()
runpy.run_module("app.services.aviation_weather.route_worker", run_name="__main__")
sys.stdout = sys.__stdout__
"""
    monkeypatch.setattr(module, "WORKER_COMMAND", (sys.executable, "-c", program))
    result = await module.evaluate_in_worker(context(), COLLECTION)
    import json

    limits = json.loads(result.reason)
    assert limits == {
        "cpu": [5, 5],
        "ram": [536870912, 536870912],
        "affinity": 1,
        "threads": ["1", "1"],
    }


async def test_normalized_collection_limit_applies_before_worker_start(children):
    with pytest.raises(WeatherUnavailable):
        await decoder().evaluate_in_worker(
            context(), {"features": [], "padding": "x" * (16 * 1024**2)}
        )
    assert children == []
