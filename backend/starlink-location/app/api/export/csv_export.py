"""CSV export endpoint for Starlink telemetry data."""

import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.core.limiter import limiter
from app.core.logging import get_logger
from .prometheus import (
    EXPORT_METRICS,
    calculate_step,
    query_all_metrics,
)

logger = get_logger(__name__)

router = APIRouter()

# CSV column headers
CSV_COLUMNS = ["timestamp"] + [col for _, col in EXPORT_METRICS]


def generate_csv(data_by_timestamp: dict[float, dict[str, float]]) -> str:
    """Generate CSV content from metric data.

    Args:
        data_by_timestamp: Dict mapping timestamp -> {column_name: value}

    Returns:
        CSV content as string
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(CSV_COLUMNS)

    # Write data rows sorted by timestamp
    for ts in sorted(data_by_timestamp.keys()):
        row_data = data_by_timestamp[ts]
        row = [datetime.utcfromtimestamp(ts).isoformat() + "Z"]
        for _, col in EXPORT_METRICS:
            row.append(row_data.get(col, ""))
        writer.writerow(row)

    return output.getvalue()


@router.get("/starlink-csv", summary="Export Starlink telemetry to CSV")
@limiter.limit("10/minute")
async def export_starlink_csv(
    request: Request,
    start: datetime = Query(..., description="Start datetime (ISO 8601)"),
    end: datetime = Query(..., description="End datetime (ISO 8601)"),
    step: Optional[int] = Query(
        None,
        description="Step interval in seconds (auto-calculated if not provided)",
        ge=1,
    ),
) -> StreamingResponse:
    """Export Starlink telemetry data to CSV.

    Queries Prometheus for historical telemetry data within the specified
    date range and returns a CSV file with all available metrics.

    Args:
        request: FastAPI request object (required for rate limiting)
        start: Start datetime for export range
        end: End datetime for export range
        step: Optional step interval in seconds (1s minimum, auto-calculated if not provided)

    Returns:
        StreamingResponse with CSV file download

    Raises:
        HTTPException: 400 if start >= end, 500 on query errors
    """
    # Validate date range
    if start >= end:
        raise HTTPException(
            status_code=400,
            detail="Start datetime must be before end datetime",
        )

    # Calculate step
    actual_step = calculate_step(start, end, step)

    logger.info(
        "Starting Starlink CSV export: start=%s end=%s step=%s",
        start.isoformat(),
        end.isoformat(),
        actual_step,
    )

    try:
        # Query all metrics from Prometheus
        data = await query_all_metrics(start, end, actual_step)

        if not data:
            raise HTTPException(
                status_code=404,
                detail="No data found for the specified time range",
            )

        # Generate CSV
        csv_content = generate_csv(data)

        # Format filename
        start_str = start.strftime("%Y%m%d-%H%M%S")
        end_str = end.strftime("%Y%m%d-%H%M%S")
        filename = f"starlink-export-{start_str}-{end_str}.csv"

        logger.info(
            "Starlink CSV export complete: filename=%s rows=%d",
            filename,
            len(data),
        )

        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to export Starlink CSV: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to query Prometheus: {str(e)}",
        )
