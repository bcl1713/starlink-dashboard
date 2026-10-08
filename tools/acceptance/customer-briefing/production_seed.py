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
"""


def kml(start, duration, wide=False):
    coordinates = (
        [(-105, 35), (-102, 35), (-99, 35)]
        if not wide
        else [(-170, 35), (-100, 35), (-30, 35), (40, 35)]
    )
    points = []
    for index, (longitude, latitude) in enumerate(coordinates):
        time = start + duration * index / (len(coordinates) - 1)
        clock = time.strftime("%Y-%m-%d %H:%M:%S") + "Z"
        points.append(
            f"<Placemark><name>Waypoint {index}</name><description>Time Over Waypoint: {clock}</description><Point><coordinates>{longitude},{latitude},10000</coordinates></Point></Placemark>"
        )
    line = " ".join(
        f"{longitude},{latitude},10000" for longitude, latitude in coordinates
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Synthetic production acceptance route</name>'
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
        "subminute": {"subminute": True},
        "nested-outage": {"nested": True},
        "ar-sof": {"ar": True},
        "adjusted": {"adjusted": True},
        "two-page": {"dense": 12},
        "three-page": {"dense": 28},
        "five-leg": {"legs": 5},
        "over-budget": {"dense": 100},
        "missing-map": {"wide": True},
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
                    "X-Unspecified" if recipe.get("unknown") else "X-Acceptance"
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
                # An unspecified X position preserves uncertainty; known X is
                # explicitly taken down by a configured same-satellite transition.
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
            leg = {
                "id": f"{mission_id}-leg-{number+1}",
                "name": f"Synthetic {name} leg {number+1}",
                "route_id": f"{mission_id}-route-{number+1}",
                "transports": transports,
            }
            if recipe.get("adjusted"):
                leg["adjusted_departure_time"] = stamp(start + timedelta(hours=2))
            legs.append(leg)
            routes.append(kml(start, duration, recipe.get("wide", False)))
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
                multipart=(leg["route_id"] + ".kml", route),
            )
            uploads.append(json.loads(body))
        actual, _, _ = api.request("GET", f"/api/v2/missions/{mission_id}")
        saved[name] = json.loads(actual)
        (root / f"seed-{name}.json").write_text(
            json.dumps(
                {
                    "submitted": mission,
                    "created": json.loads(created),
                    "uploads": uploads,
                    "actual": saved[name],
                },
                indent=2,
            )
        )
    return saved
