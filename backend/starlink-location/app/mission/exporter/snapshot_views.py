"""Private model copies and read-only manager adapters for legacy exporters."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.mission.models import Mission, MissionLeg, MissionLegTimeline
from app.models.poi import POI
from app.models.route import ParsedRoute
from app.satellites.catalog import Satellite, SatelliteCatalog

if TYPE_CHECKING:
    from .snapshot import ExportSnapshot
from .snapshot_inputs import SourcePayload


@dataclass(frozen=True)
class RouteView:
    sources: tuple[SourcePayload, ...]

    def get_route(self, route_id: str) -> ParsedRoute | None:
        item = next((p for p in self.sources if p.name == f"route/{route_id}"), None)
        return (
            ParsedRoute.model_validate_json(item.content)
            if item and item.content != b"null"
            else None
        )

    def list_routes(self) -> dict[str, ParsedRoute | None]:
        return {
            p.name.removeprefix("route/"): self.get_route(p.name.removeprefix("route/"))
            for p in self.sources
            if p.name.startswith("route/")
        }


@dataclass(frozen=True)
class POIView:
    payloads: tuple[bytes, ...]

    def list_pois(
        self, route_id: str | None = None, mission_id: str | None = None
    ) -> list[POI]:
        pois = [POI.model_validate_json(payload) for payload in self.payloads]
        return [
            p
            for p in pois
            if (not route_id or p.route_id == route_id)
            and (not mission_id or p.mission_id == mission_id)
        ]

    def find_global_poi_by_name(self, name: str) -> POI | None:
        return next(
            (
                p
                for p in self.list_pois()
                if p.name.strip().lower() == name.strip().lower()
                and p.route_id is None
                and p.mission_id is None
            ),
            None,
        )


def source_content(sources: tuple[SourcePayload, ...], name: str) -> bytes:
    return next(p.content for p in sources if p.name == name)


def captured_catalog(sources: tuple[SourcePayload, ...]) -> SatelliteCatalog:
    catalog = SatelliteCatalog()
    for data in json.loads(source_content(sources, "catalog")):
        catalog.add_satellite(Satellite(**data))
    return catalog


def captured_pois(sources: tuple[SourcePayload, ...]) -> POIView:
    from .snapshot_inputs import canonical_json

    return POIView(
        tuple(canonical_json(p) for p in json.loads(source_content(sources, "pois")))
    )


@dataclass(frozen=True)
class SnapshotViews:
    snapshot: ExportSnapshot

    def mission(self) -> Mission:
        return Mission.model_validate_json(self.snapshot.metadata_json)

    def leg(self, leg_id: str) -> MissionLeg:
        return MissionLeg.model_validate_json(self._leg(leg_id).leg_json)

    def _leg(self, leg_id: str):
        return next(leg for leg in self.snapshot.legs if leg.leg_id == leg_id)

    def timeline(self, leg_id: str) -> MissionLegTimeline | None:
        payload = self._leg(leg_id).timeline_json
        return MissionLegTimeline.model_validate_json(payload) if payload else None

    @property
    def route_manager(self) -> RouteView:
        return RouteView(self.snapshot.source_payloads)

    @property
    def poi_manager(self) -> POIView:
        return captured_pois(self.snapshot.source_payloads)

    def map_poi_manager(self, leg_id: str) -> POIView:
        """Replace prepared markers privately, preserving committed POI exports."""
        from app.mission.timeline_builder.pois import MISSION_POI_KINDS

        if self._leg(leg_id).preparation_origin != "rebuilt":
            return self.poi_manager
        leg = self.leg(leg_id)
        committed = self.poi_manager.list_pois()
        return POIView(
            tuple(
                p.model_dump_json().encode()
                for p in committed
                if not (
                    p.mission_id == self.snapshot.mission_id
                    and p.route_id == leg.route_id
                    and p.generated_source == "mission-timeline"
                    and p.kind in MISSION_POI_KINDS
                )
            )
            + self._leg(leg_id).map_pois
        )

    def kml(self, route_id: str) -> bytes | None:
        payload = next(
            (p for p in self.snapshot.source_payloads if p.name == f"kml/{route_id}"),
            None,
        )
        return payload.content if payload is not None else None

    def ground_entry_point(self):
        from app.services.ground_entry_point import GroundEntryPoint

        data = json.loads(source_content(self.snapshot.source_payloads, "ground_entry"))
        return GroundEntryPoint(**data) if data else None
