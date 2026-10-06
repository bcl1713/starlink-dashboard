"""One disposable normalizer at a time, reaped on timeout/cancellation."""

import asyncio
import json
import os
import sys

from app.services.overview_weather.protocol import WeatherUnavailable


async def await_owned(task):
    """Defer repeated caller cancellation until the owned cleanup is complete."""
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
    result = task.result()
    if cancelled:
        raise asyncio.CancelledError()
    return result


async def reap(process):
    if process.returncode is not None:
        await process.wait()
        return
    try:
        process.terminate()
    except ProcessLookupError:
        pass
    try:
        await asyncio.wait_for(process.wait(), 10)
    except TimeoutError:
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        await process.wait()


async def normalize_in_worker(layer, body, now):
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "app.services.aviation_weather.worker",
        layer,
        str(now),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env={**os.environ, "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"},
        start_new_session=True,
    )
    try:
        async with asyncio.timeout(120):
            output, _ = await process.communicate(body)
        if process.returncode != 0 or len(output) > 16 * 1024**2:
            raise WeatherUnavailable()
        return json.loads(output)
    except (TimeoutError, ValueError) as error:
        raise WeatherUnavailable() from error
    finally:
        await await_owned(asyncio.create_task(reap(process)))
