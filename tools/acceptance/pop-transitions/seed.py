"""Sanitized source missions uploaded through supported production APIs."""

import json
from datetime import datetime, timedelta, timezone

START = datetime(2026, 10, 25, 14, tzinfo=timezone.utc)
ROUTES = {
    "crossing": [(-118.24, 34.05), (-100, 36), (-77.49, 39.04)],
    "no-crossing": [(-118.24, 34.05), (-117, 35)],
    "dateline": [(139.69, 35.69), (179, 40), (-118.24, 34.05)],
    "overlap": [(-118.24, 34.05), (-100, 36), (-77.49, 39.04)],
    "continuation": [(-118.24, 34.05), (-100, 36), (-77.49, 39.04)],
}


def stamp(value):
    return value.isoformat().replace("+00:00", "Z")


def route_kml(points):
    vertices = []
    for index, (lon, lat) in enumerate(points):
        time = START + timedelta(hours=4 * index / (len(points) - 1))
        clock = time.strftime("%Y-%m-%d %H:%M:%SZ")
        vertices.append(
            f"<Placemark><name>Waypoint {index}</name><description>Time Over Waypoint: {clock}</description><Point><coordinates>{lon},{lat},10000</coordinates></Point></Placemark>"
        )
    line = " ".join(f"{lon},{lat},10000" for lon, lat in points)
    return (
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
        + "".join(vertices)
        + f"<Placemark><name>Route</name><LineString><coordinates>{line}</coordinates></LineString></Placemark></Document></kml>"
    ).encode()


def seed(api, root):
    result = {}
    for name, points in ROUTES.items():
        mission_id = "pop-acceptance-" + name
        leg_id = mission_id + "-leg"
        transports = {
            "initial_x_satellite_id": "X-Acceptance",
            "initial_ka_satellite_ids": ["AOR"],
        }
        if name in {"overlap", "continuation"}:
            transports["ka_outages"] = [
                {
                    "id": "synthetic-ka",
                    "start_time": stamp(START),
                    "duration_seconds": 14400,
                }
            ]
            transports["aar_windows"] = [
                {
                    "id": "synthetic-sof",
                    "start_waypoint_name": "Waypoint 0",
                    "end_waypoint_name": "Waypoint 2",
                    "override_start_time": stamp(START),
                    "override_end_time": stamp(START + timedelta(hours=4)),
                }
            ]
        if name == "continuation":
            transports["ku_overrides"] = [
                {
                    "id": f"synthetic-ku-{index}",
                    "start_time": stamp(START + timedelta(minutes=8 * index)),
                    "duration_seconds": 480,
                    "reason": "Synthetic configured independent outage",
                }
                for index in range(0, 28, 2)
            ]
        mission = {
            "id": mission_id,
            "name": "Synthetic PoP " + name,
            "description": "Deterministic sanitized acceptance inputs; not operational Starshield observations",
            "legs": [
                {"id": leg_id, "name": name, "route_id": "", "transports": transports}
            ],
        }
        api.request("POST", "/api/v2/missions", data=mission)
        uploaded, _, _ = api.request(
            "PUT",
            f"/api/v2/missions/{mission_id}/legs/{leg_id}/route",
            multipart=(name + ".kml", route_kml(points)),
        )
        timeline, _, _ = api.request(
            "GET", f"/api/v2/missions/{mission_id}/legs/{leg_id}/timeline"
        )
        actual = json.loads(timeline)
        forecast = actual["pop_forecast"]
        assert forecast["status"] == "ready", forecast
        assert bool(forecast["transitions"]) == (name != "no-crossing"), forecast
        for transition in forecast["transitions"]:
            a, t, b = [
                datetime.fromisoformat(transition[key].replace("Z", "+00:00"))
                for key in ("window_start_utc", "crossing_utc", "window_end_utc")
            ]
            assert (t - a).total_seconds() == (b - t).total_seconds() == 300
        result[name] = {
            "missionId": mission_id,
            "legId": leg_id,
            "timeline": actual,
            "upload": json.loads(uploaded),
        }
    (root / "source-fixtures.json").write_text(json.dumps(result, indent=2))
    return result
