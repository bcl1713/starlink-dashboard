"""Legacy timeline publication wrapper and compatibility exports."""

from pathlib import Path

from app.mission.models import MissionLeg, MissionLegTimeline
from app.mission.timeline_builder.calculator import (
    RouteTemporalProjector,
    TimelineComputationError,
    route_takeoff_delta,
    route_with_adjusted_departure,
)
from app.mission.timeline_builder.stats import TimelineSummary
from app.mission.timeline_preparation import (
    prepare_mission_timeline,
    publish_mission_pois,
)
from app.satellites.coverage import CoverageSampler
from app.satellites.kmz_importer import load_commka_coverage
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager

APP_DIR = Path(__file__).resolve().parents[1]
_COVERAGE_SAMPLER: CoverageSampler | None = None


def build_mission_timeline(
    mission: MissionLeg,
    route_manager: RouteManager,
    poi_manager: POIManager | None = None,
    coverage_sampler: CoverageSampler | None = None,
    parent_mission_id: str | None = None,
    include_samples: bool = False,
) -> tuple[MissionLegTimeline, TimelineSummary]:
    artifacts = prepare_mission_timeline(
        mission,
        route_manager,
        poi_manager,
        coverage_sampler or _get_default_coverage_sampler(),
        parent_mission_id,
        include_samples,
    )
    if poi_manager:
        publish_mission_pois(
            artifacts, poi_manager, parent_mission_id or mission.id, mission.route_id
        )
    return artifacts.timeline, artifacts.summary


def _get_default_coverage_sampler() -> CoverageSampler | None:
    global _COVERAGE_SAMPLER
    if _COVERAGE_SAMPLER is not None:
        return _COVERAGE_SAMPLER

    coverage_path = Path("data/sat_coverage/commka.geojson")
    if not coverage_path.exists():
        kmz_candidates = [
            Path("data/sat_coverage/CommKa.kmz"),
            APP_DIR / "satellites" / "assets" / "CommKa.kmz",
        ]
        for kmz_path in kmz_candidates:
            if kmz_path.exists():
                coverage_path.parent.mkdir(parents=True, exist_ok=True)
                load_commka_coverage(kmz_path, coverage_path.parent)
                break

    if coverage_path.exists():
        _COVERAGE_SAMPLER = CoverageSampler(coverage_path)
    else:
        _COVERAGE_SAMPLER = None

    return _COVERAGE_SAMPLER


__all__ = [
    "RouteTemporalProjector",
    "TimelineComputationError",
    "TimelineSummary",
    "build_mission_timeline",
    "route_takeoff_delta",
    "route_with_adjusted_departure",
]
