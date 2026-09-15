"""Overview telemetry-history API."""

from collections.abc import Awaitable, Callable

from fastapi import APIRouter, HTTPException

router = APIRouter()
_overview_history_reader: Callable[[], Awaitable[dict]] | None = None


def set_overview_history_reader(
    reader: Callable[[], Awaitable[dict]] | None,
) -> None:
    """Set the initialized overview-history runtime reader."""
    global _overview_history_reader
    _overview_history_reader = reader


@router.get("/api/overview-history")
async def get_overview_history():
    """Return the shared bounded overview telemetry-history bundle."""
    if _overview_history_reader is None:
        raise HTTPException(
            status_code=503,
            detail="Overview history is not yet initialized",
        )
    return await _overview_history_reader()
