"""Operator-only operational timeline and local notification API."""

from fastapi import APIRouter, Query, Request

from app.operator.common import Identifier
from app.operator.event_feed import snapshot_page
from app.operator.event_sources import EventSourceAdapter
from app.operator.runtime import runtime_for


def events(
    request: Request,
    mission_id: Identifier,
    cursor: str | None = Query(None, max_length=256),
    limit: int = Query(200, ge=1, le=200),
    include_history: bool = False,
):
    from app.api.operator import require_service

    with runtime_for(request) as runtime:
        service = require_service(runtime)
        adapter = getattr(runtime, "event_source_adapter", None) or EventSourceAdapter(
            service,
            live_provider=getattr(request.app.state, "operator_live_source", None),
        )
        return snapshot_page(
            runtime,
            mission_id,
            adapter=adapter,
            cursor=cursor,
            limit=limit,
            include_history=include_history,
        )


def make_router():
    # Lazy factory keeps the existing Operator API fixture and direct module
    # imports free of an import-time cycle.
    from app.api.operator import OperatorRoute

    router = APIRouter(route_class=OperatorRoute)
    router.add_api_route("/events", events, methods=["GET"])
    return router
