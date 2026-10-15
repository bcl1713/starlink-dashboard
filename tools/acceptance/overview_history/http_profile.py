"""Opt-in ASGI CPU attribution, excluded from healthy timing distributions."""

from __future__ import annotations

import cProfile
from pathlib import Path


class HTTPProfile:
    def __init__(self, app, *, output: Path):
        self.app = app
        self.output = output

    async def __call__(self, scope, receive, send):
        selected = (
            scope["type"] == "http"
            and scope["path"] == "/api/overview-history"
            and (b"x-overview-cpu-profile", b"1") in scope["headers"]
        )
        if not selected:
            return await self.app(scope, receive, send)
        profiler = cProfile.Profile()
        profiler.enable()
        try:
            await self.app(scope, receive, send)
        finally:
            profiler.disable()
            profiler.dump_stats(str(self.output))
