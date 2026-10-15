"""Prepare a detached ordinary mission; no canonical mission writes."""

import base64
import hashlib
from pathlib import Path

from app.mission.models import Mission
from app.mission.planning.extract import _parse_itinerary
from app.mission.planning.identity import planning_identity
from app.mission.planning.journal import json_bytes
from app.mission.planning.models import ItineraryData, RouteBinding

from .ar import resolve_import_ars
from .association import associate_routes
from .models import ImportIssue
from .worker import build_leg, parse_route


def prepare(service, operation):
    directory = service.store.directory(operation.id)
    payload = service.store.payload(operation.id)
    choices = payload.get("choices", {})
    parsed_path = directory / "parsed.json"
    if parsed_path.exists():
        from app.mission.planning.models import ItineraryPreview

        preview = ItineraryPreview.model_validate_json(parsed_path.read_bytes())
    else:
        preview = service.bounded(
            _parse_itinerary,
            ((directory / "source.pdf").read_bytes(),),
            operation,
            limit=10,
        )
        from app.mission.planning.journal import atomic_write

        atomic_write(parsed_path, json_bytes(preview.model_dump(mode="json")))
    data = ItineraryData.model_validate(choices.get("itinerary", preview.parsed_values))
    if data and not choices.get("itinerary"):
        # Saved unfinished corrections belong to the retained PDF. Replacing the
        # PDF deliberately starts from its new extraction instead.
        for leg in data.expected_legs:
            pending = [
                p
                for p in payload.get("pending_legs", [])
                if p["ordinal"] == leg.ordinal
                and p["departure_airport"] == leg.departure_airport
                and p["arrival_airport"] == leg.arrival_airport
            ]
            if len(pending) == 1:
                from app.mission.planning.models import ExpectedLeg

                data.expected_legs[data.expected_legs.index(leg)] = (
                    ExpectedLeg.model_validate(pending[0])
                )
    if data:
        for leg in data.expected_legs:
            if leg.draft and leg.draft.ar_corrections:
                leg.ar_rows = [
                    row.model_copy(deep=True) for row in leg.draft.ar_corrections
                ]
    issues = [
        ImportIssue(code=e.code, message=e.message, field=e.field)
        for e in preview.field_errors
    ]
    if choices.get("itinerary"):
        issues = []
    if data is None or not data.expected_legs:
        return None, issues or [
            ImportIssue(
                code="missing_itinerary", message="Correct the itinerary source."
            )
        ]
    service.stage(operation, "matching_routes")
    routes = {}
    for item in payload["files"]:
        route = service.bounded(
            parse_route, (str(directory / f"{item['id']}.kml"),), operation, limit=60
        )
        route.route_id = item["id"]
        route.content_hash = hashlib.sha256(
            (directory / f"{item['id']}.kml").read_bytes()
        ).hexdigest()
        route.metadata.file_path = str(
            service.route_manager.routes_dir / f"{item['id']}.kml"
        )
        routes[item["id"]] = route
    from .retained import reuse_routes

    reuse_routes(service, operation, data, routes, payload, directory)
    from app.mission.planning.journal import atomic_write

    review = {
        "itinerary": data.model_dump(mode="json"),
        "routes": [
            {"id": item["id"], "name": item["name"]} for item in payload["files"]
        ],
    }
    atomic_write(directory / "review.json", json_bytes(review))
    association = associate_routes(data.expected_legs, routes)
    assignments = {**association.assignments, **choices.get("routes", {})}
    if len(set(assignments.values())) != len(assignments):
        raise ValueError("A route can belong to only one leg")
    for leg_id, rid in assignments.items():
        if leg_id not in {l.id for l in data.expected_legs} or rid not in routes:
            raise ValueError("Invalid route correction")
    issues.extend(
        issue
        for issue in association.issues
        if issue.leg_id not in assignments
        and not (issue.route_id in choices.get("ignored_routes", []))
    )
    environment = service.environment()
    positions = environment["satellites"]
    if not positions or any(not p["eligible"] for p in positions):
        issues.append(
            ImportIssue(
                code="satellite_configuration",
                message="Configure valid X-band satellite positions.",
            )
        )
    expected = []
    artifacts = []
    evidence = {}
    for source in data.expected_legs:
        if source.id not in assignments:
            continue
        leg = source.model_copy(deep=True)
        route = routes[assignments[leg.id]]
        leg.route = RouteBinding(
            route_id=route.route_id,
            source_id=route.route_id,
            content_hash=route.content_hash,
            filename=Path(route.metadata.file_path).name,
        )
        ar = resolve_import_ars(leg, route, choices.get("ars", {}))
        review.setdefault("ar_options", {}).update(
            {id: entry.get("candidate_pairs", []) for id, entry in ar.evidence.items()}
        )
        atomic_write(directory / "review.json", json_bytes(review))
        leg.ar_rows = ar.rows
        issues.extend(ar.issues)
        if leg.ar_section_status == "unrecognized":
            issues.append(
                ImportIssue(
                    code="ar_section_unrecognized",
                    leg_id=leg.id,
                    message="Correct the unrecognized AR section.",
                )
            )
        expected.append(leg)
        evidence[leg.id] = {
            "association": association.evidence.get(leg.id, {}),
            "ars": ar.evidence,
            "source_leg": source.model_dump(mode="json"),
        }
    if issues:
        return None, issues
    service.stage(operation, "building_plans")
    for leg in expected:
        artifacts.append(
            service.bounded(
                build_leg,
                (
                    leg.model_dump(mode="json"),
                    routes[assignments[leg.id]].model_dump(mode="json"),
                    positions,
                    environment["constraints"],
                    str(service.mission_root),
                    operation.mission_id,
                ),
                operation,
            )
        )
    service.stage(operation, "preparing_mission")
    mission = Mission(
        id=operation.mission_id,
        name=data.name,
        legs=[item["leg"] for item in artifacts],
    )
    mission.metadata["itinerary_import"] = {
        "version": 1,
        "revision": 1,
        "operation_id": operation.id,
        "sources": {
            "pdf": hashlib.sha256((directory / "source.pdf").read_bytes()).hexdigest(),
            "routes": {id: r.content_hash for id, r in routes.items()},
        },
        "evidence": evidence,
        "baseline": {
            "name": mission.name,
            "legs": [l.model_dump(mode="json") for l in mission.legs],
        },
        "history": [],
    }
    return {
        "mission": mission.model_dump(mode="json"),
        "routes": [r.model_dump(mode="json") for r in routes.values()],
        "route_payloads": {
            rid: base64.b64encode((directory / f"{rid}.kml").read_bytes()).decode()
            for rid in routes
        },
        "artifacts": artifacts,
        "environment": environment,
        "identity": planning_identity(mission),
    }, []
