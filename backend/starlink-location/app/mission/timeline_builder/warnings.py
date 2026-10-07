"""Planned shutdown and turn-on boundaries for X-band geometry warnings."""

from dataclasses import dataclass

from app.mission.timeline_builder.coverage import RouteSample


@dataclass(frozen=True)
class XBandWarningBoundary:
    sample: RouteSample
    satellite_id: str
    warning: bool
    reasons: tuple[str, ...] = ()
