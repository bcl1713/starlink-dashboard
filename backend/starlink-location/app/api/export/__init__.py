"""Export API module - CSV export of Starlink telemetry data."""

from fastapi import APIRouter

from . import csv_export

# Create the main export router
router = APIRouter(prefix="/api/export")
router.include_router(csv_export.router)

__all__ = ["router"]
