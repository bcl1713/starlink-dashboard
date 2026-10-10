"""Read-only planning satellite configuration shared by selection and evaluation."""

from collections import defaultdict

from app.satellites import catalog as satellite_config

from .models import PlanningError, PlanningSatelliteOption
from .types import SatellitePosition


def satellite_options(poi_manager, satellite_catalog=None):
    catalog = satellite_catalog or satellite_config.get_satellite_catalog(
        read_only=True
    )
    configured = defaultdict(list)
    for poi in poi_manager.list_pois() if poi_manager else ():
        if (
            poi.category == "satellite"
            and poi.mission_id is None
            and poi.route_id is None
        ):
            configured[poi.name.strip().casefold()].append(poi)
    candidates = {}
    for sat in catalog.list_all():
        key = sat.satellite_id.strip().casefold()
        candidates[key] = (sat.satellite_id, sat.transport, 0, sat.longitude, False)
    for key, pois in configured.items():
        poi = pois[0]
        candidates[key] = (
            poi.name,
            poi.icon,
            poi.latitude,
            poi.longitude,
            len(pois) != 1,
        )
    result = []
    for identifier, transport, latitude, longitude, ambiguous in candidates.values():
        # A malformed configured band overrides its static fallback, but cannot
        # be represented by the public X/Ka/Ku option schema. Never invent X.
        if transport not in {"X", "Ka", "Ku"}:
            continue
        error = None
        position = None
        try:
            if ambiguous:
                raise ValueError("Multiple configured satellites share this identifier")
            position = SatellitePosition(
                satellite_id=identifier, latitude=latitude, longitude=longitude
            )
        except ValueError:
            error = PlanningError(
                code="satellite_position_missing",
                message=(
                    "Remove duplicate satellite identifiers in satellite configuration."
                    if ambiguous
                    else "Configure a valid latitude and longitude for this satellite."
                ),
                action="edit_satellite",
            )
            position = None
        result.append(
            PlanningSatelliteOption(
                id=identifier,
                label=identifier,
                transport=transport,
                latitude=position.latitude if position else None,
                longitude=position.longitude if position else None,
                eligible=transport == "X" and position is not None,
                error=error,
            )
        )
    return result


def resolve_positions(ids, poi_manager, satellite_catalog=None):
    options = {sat.id: sat for sat in satellite_options(poi_manager, satellite_catalog)}
    positions = []
    for identifier in sorted(ids):
        sat = options.get(identifier)
        if sat is None or not sat.eligible:
            raise ValueError(
                f"Missing or invalid configured X satellite position: {identifier}"
            )
        positions.append(
            SatellitePosition(
                satellite_id=identifier, latitude=sat.latitude, longitude=sat.longitude
            )
        )
    if not positions:
        raise ValueError("Permitted satellite positions are required")
    return tuple(positions)
