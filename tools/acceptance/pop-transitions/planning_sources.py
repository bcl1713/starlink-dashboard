"""Register synthetic planning routes through the live application's public API."""

import json
import runpy
from urllib.request import Request


def accept_sources(api, tools, records, route_kml, routes):
    """Public acceptance updates the running RouteManager before leg projection."""
    prefix = "/api/v2/missions/planning"
    pdf = runpy.run_path(str(tools.parent / "itinerary-planning/seed.py"))["pdf"](1, 1)
    for name, item in sorted(records.items()):
        body, _, _ = api.request(
            "POST", prefix + "/itinerary-previews", multipart=(name + ".pdf", pdf)
        )
        preview = json.loads(body)
        body, _, _ = api.request(
            "POST",
            prefix + "/missions",
            data={
                "preview_id": preview["preview_id"],
                "itinerary": preview["parsed_values"],
                "idempotency_key": "pop-" + name,
            },
        )
        view = json.loads(body)
        planning_id = view["mission"]["id"]
        leg_id = view["expected_legs"][0]["leg"]["id"]
        path = f"{prefix}/missions/{planning_id}/legs/{leg_id}"
        boundary = "pop-owned-planning-route"
        content = (
            (
                f'--{boundary}\r\nContent-Disposition: form-data; name="expected_revision"\r\n\r\n{view["revision"]}\r\n'
                f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}.kml"\r\nContent-Type: application/vnd.google-earth.kml+xml\r\n\r\n'
            ).encode()
            + route_kml(routes[name])
            + f"\r\n--{boundary}--\r\n".encode()
        )
        with api.opener.open(
            Request(
                api.origin + path + "/route-previews",
                data=content,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                method="POST",
            ),
            timeout=95,
        ) as response:
            preview = json.loads(response.read())
        body, _, _ = api.request(
            "POST",
            path + "/route",
            data={
                "preview_id": preview["preview_id"],
                "expected_revision": view["revision"],
                "discrepancy_acknowledgments": [
                    error["code"] for error in preview["discrepancy_errors"]
                ],
            },
        )
        accepted = json.loads(body)
        item["expectedLeg"] = accepted["expected_legs"][0]["leg"]
        item["planningSourceMissionId"] = planning_id
