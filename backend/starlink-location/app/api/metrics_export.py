"""Read-only metrics exposition through the existing registry and serializer."""

from fastapi import APIRouter, status
from prometheus_client import generate_latest
from starlette.concurrency import run_in_threadpool

from app.core.metrics import REGISTRY

router = APIRouter(tags=["metrics"])


@router.get("/metrics", status_code=status.HTTP_200_OK)
async def get_metrics(route_manager=None, poi_manager=None) -> str:
    """Serialize published metrics; legacy manager arguments are ignored."""
    return await run_in_threadpool(_prepare_metrics, route_manager, poi_manager)


def _prepare_metrics(route_manager=None, poi_manager=None) -> str:
    """Keep the frozen instrumentation entry point and existing EOF contract."""
    output = generate_latest(REGISTRY).decode("utf-8")
    if not output.endswith("# EOF\n"):
        output = output.rstrip() + "\n# EOF\n"
    return output
