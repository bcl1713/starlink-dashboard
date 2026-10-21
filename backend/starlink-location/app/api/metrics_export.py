"""Read-only metrics exposition through the existing registry and serializer."""

from threading import Lock

from fastapi import APIRouter, status
from prometheus_client import generate_latest
from starlette.concurrency import run_in_threadpool

from app.core.metrics import REGISTRY

router = APIRouter(tags=["metrics"])
_exposition_lock = Lock()
_exposition_error: str | None = None


def get_exposition_error() -> str | None:
    """Return the last completed exposition outcome, without retaining exceptions."""
    with _exposition_lock:
        return _exposition_error


def _record_exposition(error: str | None):
    global _exposition_error
    with _exposition_lock:
        _exposition_error = error


@router.get("/metrics", status_code=status.HTTP_200_OK)
async def get_metrics(route_manager=None, poi_manager=None) -> str:
    """Serialize published metrics; legacy manager arguments are ignored."""
    try:
        output = await run_in_threadpool(_prepare_metrics, route_manager, poi_manager)
    except Exception as exc:
        _record_exposition(type(exc).__name__)
        raise
    _record_exposition(None)
    return output


def _prepare_metrics(route_manager=None, poi_manager=None) -> str:
    """Keep the frozen instrumentation entry point and existing EOF contract."""
    output = generate_latest(REGISTRY).decode("utf-8")
    if not output.endswith("# EOF\n"):
        output = output.rstrip() + "\n# EOF\n"
    return output
