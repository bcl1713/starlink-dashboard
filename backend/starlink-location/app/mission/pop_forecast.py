"""Mission and live adapters for the shared advisory-only geographic forecast."""

import hashlib
import json
from datetime import datetime, timedelta
from math import isfinite
from types import SimpleNamespace

from app.mission.timeline_builder.calculator import RouteTemporalProjector
from app.models.poi import POI
from app.models.route import ParsedRoute
from app.services.aviation_weather.live_encounters import _unique_projection
from app.services.eta.segment_timing import has_route_timing
from app.services.eta_calculator import ETACalculator
from app.services.pop.forecast import build_forecast
from app.services.pop.geometry import PopGeometryError, find_crossings
from app.services.pop.models import PopCatalog, PopForecast, RouteVertex


def _result(revision, catalog, status, reason=None):
    return PopForecast(
        revision=revision,
        catalog_fingerprint=catalog.fingerprint if catalog else "",
        status=status,
        reason=reason,
    )


def _crossings(route, catalog, revision):
    if catalog is None or not catalog.sites or not catalog.fingerprint:
        raise ValueError("Missing PoP catalog")
    if route is None or len(route.points) < 2:
        raise ValueError("Missing route geometry")
    vertices = tuple(
        RouteVertex(latitude=p.latitude, longitude=p.longitude) for p in route.points
    )
    if route.get_total_distance() <= 0:
        raise ValueError("Route has no distance")
    return find_crossings(vertices, catalog, revision)


def forecast_for_mission(
    route: ParsedRoute,
    projector: RouteTemporalProjector,
    catalog: PopCatalog,
    *,
    revision: str,
    starshield_enabled: bool,
) -> PopForecast:
    """Use the effective route's existing piecewise timing, including anchors."""
    if not starshield_enabled:
        return _result(revision, catalog, "disabled")
    try:
        crossings = _crossings(route, catalog, revision)
        if projector is None or projector.route_snapshot != route.model_dump():
            raise ValueError("Timing projection belongs to a different route revision")
        if (
            projector.start_time.utcoffset() is None
            or projector.end_time.utcoffset() is None
            or projector.end_time <= projector.start_time
        ):
            raise ValueError("Unavailable route timing bounds")
    except PopGeometryError as exc:
        return _result(revision, catalog, "indeterminate", exc.reason)
    except (ValueError, TypeError, AttributeError, ArithmeticError) as exc:
        return _result(revision, catalog, "unavailable", str(exc))
    return build_forecast(
        crossings,
        projector.timestamp_for_distance,
        revision=revision,
        catalog_fingerprint=catalog.fingerprint,
    )


def mission_forecast_revision(
    route: ParsedRoute, projector: RouteTemporalProjector, catalog: PopCatalog | None
) -> str:
    """Content-address effective geometry/timing/catalog to exclude obsolete results."""
    content = [
        route.model_dump(mode="json"),
        projector.start_time.isoformat(),
        projector.end_time.isoformat(),
        catalog.fingerprint if catalog else None,
    ]
    return hashlib.sha256(
        json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def forecast_for_live(
    route: ParsedRoute,
    catalog: PopCatalog,
    *,
    revision: str,
    starshield_enabled: bool,
    now: datetime,
    latitude: float,
    longitude: float,
    speed_knots: float,
    telemetry_valid: bool,
    eta_calculator: ETACalculator | None = None,
) -> PopForecast:
    """Use current route-aware ETA; caller supplies existing freshness/validity.

    Revision identifies the route lifecycle, not each telemetry sample. Crossing
    IDs therefore survive ETA updates so live consumers can retain overdue records.
    No planned-time or direct-distance fallback is allowed.
    """
    if not starshield_enabled:
        return _result(revision, catalog, "disabled")
    try:
        crossings = _crossings(route, catalog, revision)
        if not telemetry_valid or now.utcoffset() is None:
            raise ValueError("Unavailable current telemetry")
        RouteVertex(latitude=latitude, longitude=longitude)
        if not isfinite(speed_knots) or speed_knots < 0.5:
            raise ValueError("Unavailable live speed")
        if not has_route_timing(route):
            raise ValueError("Unavailable route timing")
        calculator = eta_calculator or ETACalculator()
        projection = _unique_projection(
            route, SimpleNamespace(latitude=latitude, longitude=longitude), calculator
        )
        distance = (
            route.get_total_distance() * projection["projected_route_progress"] / 100
        )
        upcoming = tuple(c for c in crossings if c.distance_meters > distance + 1e-6)
        by_distance = {c.distance_meters: c for c in upcoming}

        def timestamp_for_distance(distance):
            crossing = by_distance[distance]
            destination = POI(
                id=crossing.id,
                name="PoP boundary",
                latitude=crossing.latitude,
                longitude=crossing.longitude,
                projected_latitude=crossing.latitude,
                projected_longitude=crossing.longitude,
                projected_waypoint_index=crossing.segment_index,
                projected_route_progress=100 * distance / route.get_total_distance(),
            )
            seconds = calculator._calculate_route_aware_eta_estimated(
                latitude, longitude, destination, route, speed_knots
            )
            if seconds is None or not isfinite(seconds) or seconds <= 0:
                raise ValueError("Unavailable current route ETA")
            return now + timedelta(seconds=seconds)

        return build_forecast(
            upcoming,
            timestamp_for_distance,
            revision=revision,
            catalog_fingerprint=catalog.fingerprint,
        )
    except PopGeometryError as exc:
        return _result(revision, catalog, "indeterminate", exc.reason)
    except (ValueError, TypeError, AttributeError, ArithmeticError, LookupError) as exc:
        return _result(revision, catalog, "unavailable", str(exc))


def configured_forecast_for_mission(
    route: ParsedRoute,
    projector: RouteTemporalProjector,
    *,
    starshield_enabled: bool,
) -> PopForecast:
    """Capture the configured catalog once for this synchronous preparation."""
    from app.core.config import ConfigManager
    from app.services.pop.catalog import load_catalog

    catalog = None
    error = None
    if starshield_enabled:
        try:
            catalog = load_catalog(ConfigManager().get_config().pop.catalog_path)
        except (OSError, ValueError) as exc:
            error = str(exc)
    revision = mission_forecast_revision(route, projector, catalog)
    if error is not None:
        return _result(
            revision, catalog, "unavailable", f"Unavailable PoP catalog: {error}"
        )
    return forecast_for_mission(
        route,
        projector,
        catalog,
        revision=revision,
        starshield_enabled=starshield_enabled,
    )
