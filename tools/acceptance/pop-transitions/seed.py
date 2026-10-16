"""Sanitized source missions uploaded through supported production APIs."""

import base64
import json
import runpy
from datetime import datetime, timedelta, timezone

START = datetime(2026, 10, 25, 14, tzinfo=timezone.utc)
ROUTES = {
    "crossing": [(-118.24, 34.05), (-100, 36), (-77.49, 39.04)],
    "no-crossing": [(-118.24, 34.05), (-117, 35)],
    "dateline": [(139.69, 35.69), (179, 40), (-118.24, 34.05)],
    "overlap": [(-118.24, 34.05), (-100, 36), (-77.49, 39.04)],
    "sole": [(-110, 35), (-104, 36)],
    "ka-alternative": [(-110, 35), (-104, 36)],
    "x-fallback": [(-110, 35), (-104, 36)],
    "concurrency-hard": [(-110, 35), (-104, 36)],
    "partial-ka": [(-110, 35), (-104, 36)],
    "unknown": [(-110, 35), (-104, 36)],
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
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>AAAA-BBBB</name>'
        + "".join(vertices)
        + f"<Placemark><name>Route</name><LineString><coordinates>{line}</coordinates></LineString></Placemark></Document></kml>"
    ).encode()


CONDITIONAL = {"sole", "ka-alternative", "x-fallback", "concurrency-hard", "partial-ka"}


def seed(api, root):
    result = {}
    for name, points in ROUTES.items():
        mission_id = "pop-acceptance-" + name
        leg_id = mission_id + "-leg"
        transports = {
            "initial_x_satellite_id": "X-Acceptance",
            "initial_ka_satellite_ids": ["AOR"],
        }
        if name in CONDITIONAL | {"unknown"}:
            transports["initial_x_satellite_id"] = {
                "x-fallback": "X-Concurrency",
                "concurrency-hard": "X-Concurrency-Hard",
                "unknown": "X-Unspecified",
            }.get(name, "X-Blocked")
            if name != "ka-alternative":
                transports["ka_outages"] = [
                    {
                        "id": "known-ka",
                        "start_time": stamp(START),
                        "duration_seconds": 14400,
                    }
                ]
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


def capture_conditional(api, owner, tools, fixtures):
    """Persist real image-generated planning records through the ordinary leg API."""
    records = {name: fixtures[name] for name in CONDITIONAL}
    # Ka recovery is aligned to the independently captured geometric crossing.
    item = records["partial-ka"]
    transition = item["timeline"]["pop_forecast"]["transitions"][0]
    raw, _, _ = api.request("GET", f"/api/v2/missions/{item['missionId']}")
    leg = json.loads(raw)["legs"][0]
    leg["transports"]["ka_outages"][0]["duration_seconds"] = (
        datetime.fromisoformat(transition["crossing_utc"].replace("Z", "+00:00"))
        - START
    ).total_seconds()
    api.request(
        "PUT", f"/api/v2/missions/{item['missionId']}/legs/{item['legId']}", data=leg
    )
    captured = json.loads(
        owner.compose(
            "exec",
            "-T",
            "--user",
            "appuser",
            "starlink-location",
            "python",
            "-c",
            (tools / "capture.py").read_text(),
            json.dumps(records),
            base64.b64encode(
                runpy.run_path(str(tools.parent / "itinerary-planning/seed.py"))["pdf"](
                    1, 1
                )
            ).decode(),
            timeout=120,
        ).splitlines()[-1]
    )
    for name, leg in captured.items():
        item = fixtures[name]
        api.request(
            "PUT",
            f"/api/v2/missions/{item['missionId']}/legs/{item['legId']}",
            data=leg,
        )
        raw, _, _ = api.request(
            "GET", f"/api/v2/missions/{item['missionId']}/legs/{item['legId']}/timeline"
        )
        item["timeline"] = json.loads(raw)
        item["capturedLeg"] = leg
        (owner.root / "source-fixtures.json").write_text(json.dumps(fixtures, indent=2))
        assert leg["transports"]["planning_policy"] == "prefer_starshield_v1"
        assert leg["transports"]["planning_inputs"]["coverage_json"] != "null"
        continuity = item["timeline"]["call_continuity"]
        assert continuity["revision"] == item["timeline"]["pop_forecast"]["revision"]
        expected = {
            "sole": 600,
            "ka-alternative": 0,
            "x-fallback": 0,
            "concurrency-hard": 600,
            "partial-ka": 300,
        }[name]
        assert abs(continuity["pop_call_outage_seconds"] - expected) < 0.001, (
            name,
            continuity,
        )
        transitions = item["timeline"]["pop_forecast"]["transitions"]
        assert len(transitions) == 1
        spans = [span for span in continuity["intervals"] if span["transition_ids"]]
        assert spans[0]["start_utc"] == transitions[0]["window_start_utc"]
        assert spans[-1]["end_utc"] == transitions[0]["window_end_utc"]
        assert not any(span["classification"] == "unknown" for span in spans), (
            name,
            spans,
        )
        for segment in item["timeline"]["segments"]:
            measured = segment["metadata"]["planning_interval"]
            assert segment["x_state"] == measured["policy_x_state"]
            assert segment["ka_state"] == measured["policy_ka_state"]
            assert segment["ku_state"] == measured["policy_ku_state"] == "available"
        if name in {"x-fallback", "concurrency-hard"}:
            for segment in item["timeline"]["segments"]:
                measured = segment["metadata"]["planning_interval"]
                assert "x_aft_cone" in measured["raw_constraints"]
                assert measured["policy_x_state"] == "offline"
                assert measured["physical_x_state"] == (
                    "available" if name == "x-fallback" else "degraded"
                )
            assert {span["classification"] for span in spans} == (
                {"x_fallback"} if name == "x-fallback" else {"planned_outage"}
            )
    unknown = fixtures["unknown"]["timeline"]["call_continuity"]
    assert any(span["classification"] == "unknown" for span in unknown["intervals"])
    (owner.root / "source-fixtures.json").write_text(json.dumps(fixtures, indent=2))
    return fixtures
