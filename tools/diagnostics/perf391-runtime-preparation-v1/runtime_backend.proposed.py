"""Proposed diagnostic image entrypoint. Import only after runtime authorization."""

import json
import os
from pathlib import Path
import re


def create_app():
    run = os.environ["PERF391_RUN"]
    role = os.environ["PERF391_ROLE"]
    if (
        os.environ.get("PERF_SYNTHETIC") != "1"
        or role not in ("A", "C")
        or not re.fullmatch(r"synthetic-[A-Za-z0-9_-]{1,22}", run)
        or os.environ.get("STARLINK_MODE") != "simulation"
    ):
        raise RuntimeError("isolated synthetic diagnostic runtime required")
    import backend_probe as probe
    from diagnostic_app import Boundary

    probe.configure(role, run, capacity=8192)
    # These files are exact frozen exports, not imports from the primary tree.
    from strict_performance.fixture import app, main
    from performance.state import capture
    from app.core.metrics import prometheus_metrics
    from app.mission.storage import get_active_leg_lock
    from starlette.responses import JSONResponse

    boundary = Boundary(
        app,
        run=run,
        capture=lambda: capture(main, prometheus_metrics),
        gate=get_active_leg_lock,
    )
    output = Path("/app/data/perf391")
    output.mkdir(exist_ok=True)

    async def wrapped(scope, receive, send):
        if scope["type"] == "lifespan":
            try:
                await boundary(scope, receive, send)
            finally:
                drained = await boundary.drain(timeout=2)
                # Main's lifespan must have stopped producers before this final drain.
                # Never drain on a request path or serialize while holding its mutex.
                records = probe.drain()
                stats = probe.stats()
                stats["runtime_boundary_drained"] = drained
                total = 0
                with (output / "backend.jsonl").open("xb") as f:
                    for row in records:
                        raw = (json.dumps(row, separators=(",", ":")) + "\n").encode()
                        total += len(raw)
                        if len(raw) > 1048576 or total > 33554432:
                            raise RuntimeError("backend export byte budget")
                        f.write(raw)
                (output / "backend-stats.json").write_text(json.dumps(stats) + "\n")
        elif scope["type"] == "http" and scope.get("path") == "/api/_diagnostic/state":
            ids = [
                v
                for k, v in scope.get("headers", [])
                if k.lower() == b"x-diagnostic-id"
            ]
            valid = len(ids) == 1 and re.fullmatch(
                re.escape(run.encode()) + rb"/source/[1-9][0-9]{0,2}", ids[0]
            )
            if not valid:
                await JSONResponse(
                    {"unavailable": "synthetic source identity required"},
                    status_code=403,
                )(scope, receive, send)
            else:
                await boundary(scope, receive, send)
        else:
            await boundary(scope, receive, send)

    return wrapped
