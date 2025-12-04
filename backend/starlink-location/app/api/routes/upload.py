"""Route upload endpoint with POI import functionality."""

# FR-004: File exceeds 300 lines (304 lines) because route upload handles KML
# parsing, validation, POI extraction, storage, and route initialization.
# Splitting would fragment the upload workflow. Deferred to v0.4.0.

from pathlib import Path
from typing import Optional, Tuple

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    Query,
    UploadFile,
    Depends,
    status,
    Request,
)
from app.core.limiter import limiter

from app.core.logging import get_logger
from app.models.poi import POICreate
from app.models.route import ParsedRoute, RouteResponse, RouteWaypoint
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager
from app.mission.dependencies import get_route_manager, get_poi_manager
from app.services.kml_parser import parse_kml_file, KMLParseError

logger = get_logger(__name__)

router = APIRouter()


def _resolve_waypoint_metadata(
    waypoint: RouteWaypoint, fallback_index: int
) -> Tuple[str, str, str, Optional[str]]:
    """Map a RouteWaypoint role to POI category/icon and derive a safe name/description.

    Converts waypoint role information into appropriate POI metadata, selecting
    category and icon based on the waypoint's role (departure, arrival, alternate, etc.)
    and constructing a meaningful name and description.

    Args:
        waypoint: Source waypoint data containing role, name, and description
        fallback_index: Index used to build fallback name if waypoint has no name

    Returns:
        Tuple of (name, category, icon, description) where description may be None
    """
    role = (waypoint.role or "").lower()

    category = "waypoint"
    icon = "waypoint"

    if role == "departure":
        category = "departure"
        icon = "airport"
    elif role == "arrival":
        category = "arrival"
        icon = "flag"
    elif role == "alternate":
        category = "alternate"
        icon = "star"

    raw_name = (waypoint.name or "").strip()
    if raw_name:
        name = raw_name
    else:
        name = f"Waypoint {fallback_index}"

    description_parts: list[str] = []

    if waypoint.description:
        waypoint_desc = waypoint.description.strip()
        if waypoint_desc:
            description_parts.append(waypoint_desc)

    if role:
        description_parts.append(f"Role: {role}")

    description = " | ".join(description_parts) if description_parts else None

    return name, category, icon, description


def _import_waypoints_as_pois(
    route_id: str,
    parsed_route: ParsedRoute,
    poi_manager: POIManager,
) -> Tuple[int, int]:
    """Create POIs for the supplied route using its waypoint metadata.

    Iterates through all waypoints in the parsed route and creates corresponding
    POI entries. Removes any existing POIs for the route first to prevent duplicates.
    Skips waypoints with invalid coordinates.

    Args:
        route_id: Route identifier (filename stem) to associate POIs with
        parsed_route: ParsedRoute instance containing waypoint data
        poi_manager: POIManager instance for creating POIs

    Returns:
        Tuple of (created_count, skipped_count) indicating success and failure counts
    """
    if not parsed_route.waypoints:
        return 0, 0

    created = 0
    skipped = 0

    # Remove any previously imported POIs for this route to avoid duplicates
    try:
        removed = poi_manager.delete_route_pois(route_id)
        if removed:
            logger.info(
                f"Removed {removed} existing POIs prior to re-import for route "
                f"{route_id}"
            )
    except Exception as exc:
        logger.error(f"Failed to delete existing POIs for route {route_id}: {exc}")

    for idx, waypoint in enumerate(parsed_route.waypoints, start=1):
        try:
            latitude = waypoint.latitude
            longitude = waypoint.longitude

            if latitude is None or longitude is None:
                skipped += 1
                continue

            name, category, icon, description = _resolve_waypoint_metadata(
                waypoint, idx
            )

            route_note = (
                f"Imported from route {parsed_route.metadata.name}"
                if parsed_route.metadata.name
                else "Imported from uploaded KML"
            )
            if description:
                description = f"{description} | {route_note}"
            else:
                description = route_note

            poi = POICreate(
                name=name,
                latitude=latitude,
                longitude=longitude,
                icon=icon,
                category=category,
                description=description,
                route_id=route_id,
            )
            poi_manager.create_poi(poi)
            created += 1
        except Exception as exc:
            logger.error(
                f"Failed to create POI for waypoint {waypoint.name or idx} on "
                f"route {route_id}: {exc}"
            )
            skipped += 1

    return created, skipped


@router.post(
    "/upload",
    response_model=RouteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload KML route",
)
@limiter.limit("10/minute")
async def upload_route(
    request: Request,
    import_pois: bool = Query(
        default=True,
        description="Import POIs from waypoint placemarks in the uploaded KML",
    ),
    file: UploadFile = File(...),
    route_manager: RouteManager = Depends(get_route_manager),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> RouteResponse:
    """Upload a new KML route file.

    Accepts a KML file upload, parses it, stores it in the routes directory,
    and optionally imports waypoint placemarks as POIs. Handles filename
    conflicts by appending a counter suffix.

    Args:
        request: FastAPI request object (required for rate limiting)
        import_pois: Whether to import waypoint placemarks as POIs (default: True)
        file: Uploaded KML file (multipart/form-data)
        route_manager: Injected RouteManager dependency for route operations
        poi_manager: Injected POIManager dependency for POI import

    Returns:
        RouteResponse containing route metadata, timing profile, and import statistics

    Raises:
        HTTPException: 400 if file is invalid or parse fails, 500 if upload fails
    """
    if not route_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Route manager not initialized",
        )

    # Validate file extension
    if not file.filename or not file.filename.endswith(".kml"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .kml files are allowed",
        )

    try:
        # Ensure we write uploads to the active RouteManager directory
        routes_dir = Path(getattr(route_manager, "routes_dir", "/data/routes"))
        routes_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename (handle conflicts)
        file_path = routes_dir / file.filename
        counter = 1
        base_path = file_path

        while file_path.exists():
            stem = base_path.stem
            file_path = routes_dir / f"{stem}-{counter}.kml"
            counter += 1

        # Write file to disk
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        logger.info(f"KML file uploaded: {file.filename} (size: {len(content)} bytes)")

        # Get parsed route
        route_id = file_path.stem

        # Explicitly load the route file (watchdog may not pick it up in tests)
        try:
            route_manager._load_route_file(file_path)
        except Exception as e:
            logger.error(f"Error loading route file {file_path}: {str(e)}")

        parsed_route = route_manager.get_route(route_id)

        if not parsed_route:
            # Fallback: parse synchronously to avoid race conditions with
            # filesystem events
            try:
                parsed_route = parse_kml_file(file_path)
                if parsed_route:
                    route_manager.add_route(route_id, parsed_route)
            except KMLParseError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to parse KML file: {file.filename} ({exc})",
                ) from exc

        if not parsed_route:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse KML file: {file.filename}",
            )

        created_pois = skipped_pois = None

        if import_pois and poi_manager:
            created_pois, skipped_pois = _import_waypoints_as_pois(
                route_id, parsed_route, poi_manager
            )
            logger.info(
                "Imported %d POIs (skipped %d) from KML placemarks for route %s",
                created_pois,
                skipped_pois,
                route_id,
            )

        has_timing_data = False
        flight_phase = None
        if parsed_route.timing_profile:
            has_timing_data = parsed_route.timing_profile.has_timing_data
            flight_phase = parsed_route.timing_profile.flight_status

        return RouteResponse(
            id=route_id,
            name=parsed_route.metadata.name,
            description=parsed_route.metadata.description,
            point_count=parsed_route.metadata.point_count,
            is_active=False,
            imported_at=parsed_route.metadata.imported_at,
            imported_poi_count=created_pois,
            skipped_poi_count=skipped_pois,
            has_timing_data=has_timing_data,
            timing_profile=parsed_route.timing_profile,
            flight_phase=flight_phase,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading route {file.filename}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading route: {str(e)}",
        )
