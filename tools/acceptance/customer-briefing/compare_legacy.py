#!/usr/bin/env python3
"""Generate/compare real legacy packages on identical invented, fixed-clock inputs.

Run "generate BACKEND_ROOT OUTPUT_DIRECTORY" once per source revision, then
"compare BASELINE_OUTPUT CANDIDATE_OUTPUT REPORT_PATH". No dashboard, browser,
Docker, external screenshot service or production data is involved.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import zipfile
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

BASE = datetime(2026, 10, 7, 8, tzinfo=timezone.utc)


class ClockMeta(type):
    def __instancecheck__(cls, instance):
        return isinstance(instance, datetime)


class FixedClock(datetime, metaclass=ClockMeta):
    @classmethod
    def now(cls, tz=None):
        return BASE.astimezone(tz) if tz else BASE.replace(tzinfo=None)


def generate(backend: Path, output: Path) -> None:
    sys.path.insert(0, str(backend.resolve()))
    import numpy as np

    import app.mission.exporter as export_module
    import app.satellites.catalog as catalog_module
    import app.services.poi.manager as poi_module
    from app.mission import models, storage, timeline_service
    from app.mission.exporter import __main__ as exporter
    from app.mission.models import (
        AARWindow,
        KaOutage,
        ManualAARTrack,
        ManualAARTrackPoint,
        ManualRouteSplice,
        Mission,
        MissionLeg,
        TransportConfig,
    )
    from app.mission.package import __main__ as package
    from app.models.poi import POI
    from app.models.route import (
        ParsedRoute,
        RouteMetadata,
        RoutePoint,
        RouteTimingProfile,
        RouteWaypoint,
    )
    from app.satellites.catalog import Satellite, SatelliteCatalog
    from app.services.poi_manager import POIManager
    from app.services.route_manager import RouteManager

    original_map, original_adjust = (
        export_module._generate_route_map,
        exporter.adjust_text,
    )

    def deterministic_map(*args, **kwargs):
        np.random.seed(1713)
        return original_map(*args, **kwargs)

    def deterministic_labels(*args, **kwargs):
        # Legacy passes "lim", which modern adjustText ignores in favor of a
        # wall-clock deadline. Pin optimization work for exact media comparison.
        kwargs.update(iter_lim=1000, time_lim=None)
        return original_adjust(*args, **kwargs)

    output.mkdir(parents=True, exist_ok=True)
    # The caller owns this directory before creation; every fixture file and
    # legacy KMZ scratch directory is scoped underneath it and removed on exit.
    with tempfile.TemporaryDirectory(prefix="legacy-inputs-", dir=output) as task_root:
        task_root = Path(task_root)
        previous_cwd, previous_tempdir = Path.cwd(), tempfile.tempdir
        tempfile.tempdir = str(task_root)
        os.chdir(task_root)
        try:
            with ExitStack() as stack:
                stack.enter_context(
                    patch.object(
                        export_module, "_generate_route_map", deterministic_map
                    )
                )
                stack.enter_context(
                    patch.object(exporter, "adjust_text", deterministic_labels)
                )
                for module in (models, storage, exporter, package, poi_module):
                    stack.enter_context(patch.object(module, "datetime", FixedClock))
                stack.enter_context(
                    patch.object(storage, "MISSIONS_DIR", task_root / "missions")
                )
                catalog = SatelliteCatalog()
                catalog.add_satellite(Satellite("X-fixture", "X", longitude=0))
                stack.enter_context(patch.object(catalog_module, "_catalog", catalog))
                for case in ("adjusted", "splice", "cached-missing"):
                    timeline_service._COVERAGE_SAMPLER = None
                    routes = RouteManager(task_root / case / "routes")
                    pois = POIManager(task_root / case / "pois.json")
                    legs = []
                    for index in range(2):
                        route_id, leg_id = f"route-{index}", f"leg-{index}"
                        route = ParsedRoute(
                            metadata=RouteMetadata(
                                name=f"Invented route {index}",
                                file_path=f"{route_id}.kml",
                                point_count=3,
                                imported_at=BASE,
                            ),
                            points=[
                                RoutePoint(
                                    latitude=lat,
                                    longitude=0,
                                    sequence=i,
                                    expected_arrival_time=BASE
                                    + timedelta(minutes=i * 30),
                                )
                                for i, lat in enumerate((0, 0.5, 1))
                            ],
                            waypoints=[
                                RouteWaypoint(
                                    name=name,
                                    latitude=lat,
                                    longitude=0,
                                    order=i,
                                    expected_arrival_time=BASE
                                    + timedelta(minutes=i * 30),
                                )
                                for i, (name, lat) in enumerate(
                                    (("DEP", 0), ("AR", 0.5), ("ARR", 1))
                                )
                            ],
                            timing_profile=RouteTimingProfile(
                                departure_time=BASE,
                                arrival_time=BASE + timedelta(hours=1),
                                has_timing_data=True,
                            ),
                        )
                        routes._routes[route_id] = route
                        (routes.routes_dir / f"{route_id}.kml").write_text(
                            f"<kml><name>{route_id}</name></kml>"
                        )
                        transport = TransportConfig(
                            initial_x_satellite_id="X-fixture",
                            ka_outages=[
                                KaOutage(
                                    id=f"outage-{index}",
                                    start_time=BASE + timedelta(minutes=20),
                                    duration_seconds=300,
                                    reason="Invented outage",
                                )
                            ],
                            aar_windows=[
                                AARWindow(
                                    id=f"ar-{index}",
                                    start_waypoint_name="AR",
                                    end_waypoint_name="ARR",
                                )
                            ],
                        )
                        if case == "splice":
                            transport.manual_aar_tracks = [
                                ManualAARTrack(
                                    id=f"track-{index}",
                                    name="Invented track",
                                    points=[
                                        ManualAARTrackPoint(
                                            latitude=0.3 if index == 0 else 70,
                                            longitude=0.01,
                                        ),
                                        ManualAARTrackPoint(
                                            latitude=0.7 if index == 0 else 71,
                                            longitude=0.01,
                                        ),
                                    ],
                                )
                            ]
                            transport.manual_route_splice = ManualRouteSplice(
                                enabled_track_id=f"track-{index}", speed_knots=100
                            )
                        leg = MissionLeg(
                            id=leg_id,
                            name=f"Invented leg {index}",
                            route_id=route_id,
                            transports=transport,
                            adjusted_departure_time=(
                                BASE + timedelta(days=index * 3, minutes=40)
                                if case == "adjusted"
                                else None
                            ),
                            created_at=BASE,
                            updated_at=BASE,
                        )
                        legs.append(leg)
                        pois._pois[f"user-{index}"] = POI(
                            id=f"user-{index}",
                            name=f"Invented user marker {index}",
                            category="mission-event",
                            mission_id=f"mission-{case}",
                            route_id=route_id,
                            latitude=0.1,
                            longitude=0,
                            created_at=BASE,
                            updated_at=BASE,
                        )
                    mission = Mission(
                        id=f"mission-{case}",
                        name=f"Invented {case} mission",
                        description="Legacy comparison; no customer data",
                        metadata={"mission_number": "26-fixture", "revision": "3"},
                        legs=legs,
                        created_at=BASE,
                        updated_at=BASE,
                    )
                    storage.save_mission_v2(mission)
                    # Pre-populate existing generated markers exactly as a saved
                    # mission would, so publication removal alone cannot change maps.
                    for leg in legs:
                        timeline, _ = timeline_service.build_mission_timeline(
                            leg, routes, pois, parent_mission_id=mission.id
                        )
                        if case == "cached-missing":
                            storage.save_mission_timeline(leg.id, timeline, mission.id)
                    if case == "cached-missing":
                        routes._routes.clear()
                        storage.delete_mission_timeline("leg-1", mission.id)
                    with package.export_mission_package(
                        mission.id, routes, pois
                    ) as stream:
                        (output / f"{case}.zip").write_bytes(stream.read())
                    # Direct download uses the unchanged established builder path.
                    if case == "adjusted":
                        timeline, _ = timeline_service.build_mission_timeline(
                            legs[0], routes, pois, parent_mission_id=mission.id
                        )
                        direct = exporter.generate_pptx_export(
                            timeline,
                            legs[0],
                            parent_mission_id=mission.id,
                            route_manager=routes,
                            poi_manager=pois,
                        )
                        (output / "direct-single-leg.pptx").write_bytes(direct)
        finally:
            os.chdir(previous_cwd)
            tempfile.tempdir = previous_tempdir


def parts(content: bytes, pptx: bool = False) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        result = {entry.filename: archive.read(entry) for entry in archive.infolist()}
    if pptx and "docProps/core.xml" in result:
        root = ET.fromstring(result["docProps/core.xml"])
        for child in list(root):
            if child.tag in (
                "{http://purl.org/dc/terms/}created",
                "{http://purl.org/dc/terms/}modified",
            ):
                root.remove(child)
        result["docProps/core.xml"] = ET.tostring(root)
    return result


def compare(baseline: Path, candidate: Path, report: Path) -> None:
    comparisons = []
    differences = []
    for before in sorted(baseline.glob("*")):
        if before.suffix not in (".zip", ".pptx"):
            continue
        after = candidate / before.name
        old, new = parts(before.read_bytes(), before.suffix == ".pptx"), parts(
            after.read_bytes(), after.suffix == ".pptx"
        )
        for name in sorted(old.keys() | new.keys()):
            if name not in old or name not in new:
                differences.append(f"{before.name}/{name}: file set changed")
            elif name.endswith(".pptx"):
                a, b = parts(old[name], True), parts(new[name], True)
                for part in sorted(a.keys() | b.keys()):
                    if a.get(part) != b.get(part):
                        differences.append(
                            f"{before.name}/{name}/{part}: content changed"
                        )
            elif old[name] != new[name]:
                differences.append(f"{before.name}/{name}: content changed")
        comparisons.append(
            {
                "fixture": before.name,
                "baseline_sha256": sha256(before.read_bytes()).hexdigest(),
                "candidate_sha256": sha256(after.read_bytes()).hexdigest(),
                "entry_count": len(old),
            }
        )
    report.write_text(
        json.dumps(
            {
                "status": "pass" if not differences else "fail",
                "comparisons": comparisons,
                "differences": differences,
                "ignored": [
                    "ZIP entry timestamps",
                    "PPTX core creation/modification properties",
                ],
                "clock": BASE.isoformat(),
                "renderer_controls": {
                    "numpy_seed_per_map": 1713,
                    "adjustText_iter_lim": 1000,
                    "adjustText_time_lim": None,
                },
                "checks": [
                    "ZIP paths",
                    "source JSON/KML/POIs",
                    "CSV bytes",
                    "all PPTX XML, geometry, palette, styles, relationships and media bytes",
                ],
            },
            indent=2,
        )
        + "\n"
    )
    print(report.read_text())
    if differences:
        raise SystemExit(1)


if __name__ == "__main__":
    mode, *args = sys.argv[1:]
    if mode == "generate" and len(args) == 2:
        generate(*(Path(a).resolve() for a in args))
    elif mode == "compare" and len(args) == 3:
        compare(*(Path(a).resolve() for a in args))
    else:
        raise SystemExit("generate BACKEND OUTPUT | compare BASELINE CANDIDATE REPORT")
