"""Locate planned restriction boundaries, then reuse the application's live ETA."""

from bisect import bisect_right
from copy import deepcopy
from datetime import timedelta
from math import isfinite

from app.models.poi import POI
from app.models.route import ParsedRoute
from app.services.aviation_weather.live_encounters import _unique_projection
from app.services.eta.segment_timing import has_route_timing
from app.services.eta_calculator import ETACalculator

from .time_models import utc_timestamp


def attach_boundary_geometry(model, artifacts):
    """Use the existing inverse temporal projector and route interpolation."""
    projector = artifacts.projector
    times = set()
    for span in model.get("capability_spans", []):
        times.update((span["start_utc"], span["end_utc"]))
    for span in (model.get("call_continuity") or {}).get("intervals", []):
        times.update((span["start_utc"], span["end_utc"]))
    boundaries = {}
    for timestamp in times:
        distance = projector.distance_for_timestamp(utc_timestamp(timestamp))
        sample = projector.sample_at_distance(distance)
        index = min(
            len(artifacts.route.points) - 2,
            max(0, bisect_right(projector.cumulative_distances, distance) - 1),
        )
        boundaries[utc_timestamp(timestamp).isoformat()] = {
            "latitude": sample.latitude,
            "longitude": sample.longitude,
            "segment_index": index,
            "progress": 100 * distance / projector.total_distance,
        }
    model["restriction_route"] = artifacts.route.model_dump(mode="json")
    model["restriction_boundaries"] = boundaries


def refresh_boundary_times(model, inputs, *, as_of):
    """No delay offsets, new transport model, or planned-time airborne fallback."""
    model = deepcopy(model)
    phase = inputs.context.get("phase")
    model["time_basis"] = "planned_utc"
    if phase == "pre_departure":
        return model, True
    model.pop("pop_forecast", None)
    model.pop("pop_advisories", None)
    model["time_basis"] = "live_unavailable"
    model["boundary_times"] = {}
    try:
        if phase != "in_flight":
            raise ValueError("Aircraft is not in flight")
        route = ParsedRoute.model_validate(model["restriction_route"])
        position = inputs.position
        if (
            not has_route_timing(route)
            or not isfinite(position.speed)
            or position.speed < 0.5
        ):
            raise ValueError("Live route timing or speed unavailable")
        calculator = ETACalculator()
        projection = _unique_projection(route, position, calculator)
        current = projection["projected_route_progress"]
        for key, boundary in model["restriction_boundaries"].items():
            if boundary["progress"] <= current + 1e-9:
                # Passed boundaries cannot remain in the future because a plan
                # was early/late. They only classify the interval as active/ended.
                model["boundary_times"][key] = as_of.isoformat()
                continue
            destination = POI(
                id="restriction-boundary",
                name="Restriction boundary",
                latitude=boundary["latitude"],
                longitude=boundary["longitude"],
                projected_latitude=boundary["latitude"],
                projected_longitude=boundary["longitude"],
                projected_waypoint_index=boundary["segment_index"],
                projected_route_progress=boundary["progress"],
            )
            seconds = calculator._calculate_route_aware_eta_estimated(
                position.latitude,
                position.longitude,
                destination,
                route,
                position.speed,
            )
            if seconds is None or not isfinite(seconds) or seconds <= 0:
                raise ValueError("Live boundary ETA unavailable")
            model["boundary_times"][key] = (
                as_of + timedelta(seconds=seconds)
            ).isoformat()
        model["time_basis"] = "live_route_eta"
        return model, True
    except (ValueError, TypeError, AttributeError, ArithmeticError, LookupError):
        model["boundary_times"] = {}
        return model, False
