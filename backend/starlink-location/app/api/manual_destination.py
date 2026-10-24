"""Persistent manual Overview destination and offline airport search."""

from fastapi import APIRouter, HTTPException, Query, Request

from app.services.manual_destination import (
    ManualDestinationSettings,
    ManualDestinationStore,
    search_airports,
)

router = APIRouter(prefix="/api/overview", tags=["overview"])


def _store(request: Request) -> ManualDestinationStore:
    store = getattr(request.app.state, "manual_destination_store", None)
    if store is None:
        raise HTTPException(
            status_code=503, detail="Manual destination settings are not initialized"
        )
    return store


@router.get("/manual-destination", response_model=ManualDestinationSettings)
async def get_manual_destination(request: Request):
    return _store(request).get()


@router.put("/manual-destination", response_model=ManualDestinationSettings)
async def put_manual_destination(request: Request, settings: ManualDestinationSettings):
    try:
        return _store(request).set(settings)
    except OSError as error:
        raise HTTPException(
            status_code=503, detail="Unable to save manual destination"
        ) from error


@router.get("/airports")
async def get_airports(q: str = Query(default="", max_length=120)):
    return {"airports": search_airports(q)}
