"""Release this HTTP request's lease on an actual ASGI disconnect."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from fastapi import Request

T = TypeVar("T")


class WeatherRequestDisconnected(Exception):
    pass


async def await_weather_request(
    request: Request, operation: Callable[[], Awaitable[T]]
) -> T:
    async def disconnect():
        while True:
            message = await request.receive()
            if message["type"] == "http.disconnect":
                return

    task = asyncio.create_task(operation())
    watcher = asyncio.create_task(disconnect())
    try:
        done, _ = await asyncio.wait(
            (task, watcher), return_when=asyncio.FIRST_COMPLETED
        )
        if watcher in done:
            raise WeatherRequestDisconnected()
        return await task
    finally:
        for owned in (task, watcher):
            if not owned.done():
                owned.cancel()
        await asyncio.gather(task, watcher, return_exceptions=True)
