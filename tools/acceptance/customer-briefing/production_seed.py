"""Deterministic supported source inputs; never inject composition snapshots."""

import json
from datetime import datetime, timedelta, timezone

BASE = datetime(2026, 10, 25, 14, tzinfo=timezone.utc)


def stamp(value):
    return value.isoformat().replace("+00:00", "Z")


def provider_seed():
    return """import json
from pathlib import Path
coverage=Path('data/sat_coverage'); coverage.mkdir(parents=True,exist_ok=True)
satellites=Path('data/satellites'); satellites.mkdir(parents=True,exist_ok=True)
polygon={'type':'Feature','properties':{'satellite_id':'AOR','fixture_kind':'synthetic provider acceptance fixture'},'geometry':{'type':'Polygon','coordinates':[[[-170,-80],[170,-80],[170,80],[-170,80],[-170,-80]]]}}
(coverage/'commka.geojson').write_text(json.dumps({'type':'FeatureCollection','features':[polygon]}))
(satellites/'catalog.yaml').write_text('satellites:\\n  - id: X-Acceptance\\n    transport: X\\n    longitude: -102\\n    slot: Synthetic acceptance provider\\n')
print(json.dumps({'fixtureKind':'synthetic provider acceptance fixture','coverage':'supported GeoJSON','catalog':'supported YAML'}))
with (satellites/'catalog.yaml').open('a') as catalog:
 catalog.write(chr(10).join(['  - id: X-Blocked','    transport: X','    longitude: 80','    slot: Synthetic geometrically blocked acceptance provider'])+chr(10))
"""


def kml(start, duration, wide=False, untimed_middle=False):
    coordinates = (
        [(-105, 35), (-102, 35), (-99, 35)]
        if not wide
        else [(-170, 35), (-100, 35), (-30, 35), (40, 35)]
    )
    points = []
    for index, (longitude, latitude) in enumerate(coordinates):
        time = start + duration * index / (len(coordinates) - 1)
        clock = time.strftime("%Y-%m-%d %H:%M:%S") + "Z"
        description = (
            "Untimed interior vertex for synthetic map fallback acceptance"
            if untimed_middle and index == 1
            else "Time Over Waypoint: " + clock
        )
        points.append(
            f"<Placemark><name>Waypoint {index}</name><description>{description}</description><Point><coordinates>{longitude},{latitude},10000</coordinates></Point></Placemark>"
        )
    line = " ".join(
        f"{longitude},{latitude},10000" for longitude, latitude in coordinates
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Synthetic production acceptance KADW-PAED route</name>'
        + "".join(points)
        + f"<Placemark><name>Flight route</name><LineString><coordinates>{line}</coordinates></LineString></Placemark></Document></kml>"
    ).encode()


def seed_missions(api, root):
    recipes = {
        "normal": {},
        "incomplete-x": {"unknown": True},
        "short": {"minutes": 10},
        "midnight": {"start": BASE + timedelta(hours=60)},
        "dst": {"start": datetime(2026, 11, 1, 5, tzinfo=timezone.utc)},
        "short-dst": {
            "start": datetime(2026, 11, 1, 5, tzinfo=timezone.utc),
            "minutes": 10,
        },
        "subminute": {"subminute": True},
        "uncertain-subminute": {"subminute": True, "uncertain": True},
        "nested-outage": {"nested": True},
        "ar-sof": {"ar": True},
        "adjusted": {"adjusted": True},
        "spliced": {"splice": True},
        "missing-timeline": {},
        "cached-missing-route": {},
        "two-page": {"dense": 12},
        "three-page": {"dense": 28},
        "five-leg": {"legs": 5},
        "over-budget": {"dense": 100},
        "missing-map": {"untimed_middle": True},
    }
    saved = {}
    for name, recipe in recipes.items():
        mission_id = "briefing-" + name
        legs, routes = [], []
        for number in range(recipe.get("legs", 1)):
            start = recipe.get("start", BASE) + timedelta(days=number)
            duration = timedelta(minutes=recipe.get("minutes", 240))
            end = start + duration
            transports = {
                "initial_x_satellite_id": (
                    "X-Unspecified"
                    if recipe.get("unknown")
                    else (
                        "X-Blocked"
                        if (recipe.get("subminute") or recipe.get("nested"))
                        and not recipe.get("uncertain")
                        else "X-Acceptance"
                    )
                ),
                "initial_ka_satellite_ids": ["AOR"],
            }
            if dense := recipe.get("dense"):
                transports["ka_outages"] = [
                    {
                        "id": "dense-ka",
                        "start_time": stamp(start),
                        "duration_seconds": duration.total_seconds(),
                    }
                ]
                transports["ku_overrides"] = [
                    {
                        "id": f"dense-ku-{i}",
                        "start_time": stamp(start + duration * i / dense),
                        "duration_seconds": duration.total_seconds() / dense,
                        "reason": "Synthetic configured acceptance outage",
                    }
                    for i in range(0, dense, 2)
                ]
            if recipe.get("subminute") or recipe.get("nested"):
                a = start + timedelta(minutes=60, seconds=1)
                transports["ka_outages"] = [
                    {
                        "id": "short-ka",
                        "start_time": stamp(a),
                        "duration_seconds": 240 if recipe.get("nested") else 4,
                    }
                ]
                transports["ku_overrides"] = [
                    {
                        "id": "short-ku",
                        "start_time": stamp(a + timedelta(seconds=2)),
                        "duration_seconds": 4,
                        "reason": "Synthetic brief nested total outage",
                    }
                ]
                # Keep the unresolved transition control distinct from confirmed
                # geometric blockage; uncertainty never proves total unavailability.
                if recipe.get("uncertain"):
                    transports["x_transitions"] = [
                        {
                            "id": "test-transition",
                            "latitude": 35,
                            "longitude": -103.5,
                            "target_satellite_id": "X-Acceptance",
                            "is_same_satellite_transition": True,
                        }
                    ]
            if recipe.get("ar"):
                transports["aar_windows"] = [
                    {
                        "id": "sof-overlap",
                        "start_waypoint_name": "Waypoint 0",
                        "end_waypoint_name": "Waypoint 2",
                        "override_start_time": stamp(start),
                        "override_end_time": stamp(end),
                    }
                ]
            if recipe.get("splice"):
                transports["manual_aar_tracks"] = [
                    {
                        "id": "synthetic-track",
                        "name": "Synthetic manual AR track",
                        "points": [
                            {"latitude": 35, "longitude": -103.5},
                            {"latitude": 37, "longitude": -102},
                            {"latitude": 35, "longitude": -100.5},
                        ],
                    }
                ]
                transports["manual_route_splice"] = {
                    "enabled_track_id": "synthetic-track",
                    "leave_segment_index": 0,
                    "leave_fraction": 0.5,
                    "rejoin_segment_index": 1,
                    "rejoin_fraction": 0.5,
                    "speed_knots": 450,
                }
            leg = {
                "id": f"{mission_id}-leg-{number+1}",
                "name": f"Synthetic {name} leg {number+1}",
                "route_id": "",
                "transports": transports,
            }
            legs.append(leg)
            routes.append(
                (
                    f"{mission_id}-route-{number+1}.kml",
                    kml(
                        start,
                        duration,
                        recipe.get("wide", False),
                        recipe.get("untimed_middle", False),
                    ),
                )
            )
        mission = {
            "id": mission_id,
            "name": f"Synthetic briefing {name}",
            "description": "Production acceptance with synthetic provider sources",
            "metadata": {"fixture_kind": "synthetic supported production inputs"},
            "legs": legs,
        }
        created, _, _ = api.request("POST", "/api/v2/missions", data=mission)
        uploads = []
        for leg, route in zip(legs, routes):
            body, _, _ = api.request(
                "PUT",
                f"/api/v2/missions/{mission_id}/legs/{leg['id']}/route",
                multipart=route,
            )
            uploads.append(json.loads(body))
            if any(
                "Timeline regeneration failed" in warning
                for warning in (uploads[-1].get("warnings") or [])
            ):
                raise ValueError(
                    "Supported route upload did not produce a timeline: "
                    + body.decode()
                )
            if recipe.get("adjusted"):
                updated = uploads[-1]["leg"]
                updated["adjusted_departure_time"] = stamp(BASE + timedelta(hours=2))
                body, _, _ = api.request(
                    "PUT",
                    f"/api/v2/missions/{mission_id}/legs/{leg['id']}",
                    data=updated,
                )
                uploads.append(json.loads(body))
        actual, _, _ = api.request("GET", f"/api/v2/missions/{mission_id}")
        saved[name] = json.loads(actual)
        source_timelines = []
        invalid_bounds = False
        for number, leg in enumerate(saved[name]["legs"]):
            timeline, _, _ = api.request(
                "GET", f"/api/v2/missions/{mission_id}/legs/{leg['id']}/timeline"
            )
            timeline = json.loads(timeline)
            source_timelines.append(timeline)
            segments = timeline["segments"]
            expected_start = recipe.get("start", BASE) + timedelta(days=number)
            if recipe.get("adjusted"):
                expected_start += timedelta(hours=2)
            expected_end = expected_start + timedelta(
                minutes=recipe.get("minutes", 240)
            )
            if (
                not segments
                or min(
                    datetime.fromisoformat(s["start_time"].replace("Z", "+00:00"))
                    for s in segments
                )
                != expected_start
                or (
                    not recipe.get("splice")
                    and max(
                        datetime.fromisoformat(s["end_time"].replace("Z", "+00:00"))
                        for s in segments
                    )
                    != expected_end
                )
            ):
                invalid_bounds = True
        (root / f"seed-{name}.json").write_text(
            json.dumps(
                {
                    "submitted": mission,
                    "created": json.loads(created),
                    "uploads": uploads,
                    "actual": saved[name],
                    "sourceTimelines": source_timelines,
                },
                indent=2,
            )
        )
        if invalid_bounds:
            raise ValueError(
                "Supported inputs did not prepare expected flight bounds: " + name
            )
    return saved
