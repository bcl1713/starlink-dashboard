#!/usr/bin/env python3
"""Exact-candidate customer briefing acceptance, with recorded scoped ownership."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def validate_candidate(root, sha):
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("full candidate SHA required")
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    if sha != head:
        raise ValueError("candidate must equal checked-out HEAD")
    if subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=root
    ):
        raise ValueError("acceptance requires a clean tracked worktree")


def claim_paths(evidence, task):
    if task.exists() or evidence.exists():
        raise ValueError(
            "task/evidence root already exists; preserve previous ownership"
        )
    if evidence == task or task in evidence.parents or evidence in task.parents:
        raise ValueError("task and durable evidence roots must be disjoint")
    evidence.mkdir(parents=True)
    write_json(
        evidence / "paths-ownership.json",
        {"task_root": str(task), "evidence_root": str(evidence)},
    )
    task.mkdir(parents=True)


class Owner:
    def __init__(self, evidence):
        self.evidence = Path(evidence)
        self.evidence.mkdir(parents=True, exist_ok=True)
        # Reap orphaned grandchildren on Linux, including killed browser workers.
        if sys.platform == "linux":
            ctypes.CDLL(None).prctl(36, 1, 0, 0, 0)

    def run(self, name, command, *, seconds=600, cwd=None, env=None):
        record = {
            "command": command,
            "cwd": str(cwd or Path.cwd()),
            "pid": None,
            "pgid": None,
            "limit_seconds": seconds,
        }
        path = self.evidence / f"{name}-ownership.json"
        write_json(path, record)
        started = time.monotonic()
        with (self.evidence / f"{name}.log").open("w") as log:
            child = subprocess.Popen(
                command,
                stdout=log,
                stderr=subprocess.STDOUT,
                cwd=cwd,
                env=env,
                start_new_session=True,
            )
            record.update(pid=child.pid, pgid=child.pid)
            write_json(path, record)
            try:
                result = child.wait(timeout=seconds)
                record["exit_code"] = result
                if result:
                    raise subprocess.CalledProcessError(result, command)
            finally:
                self.reap(child)
                record["elapsed_seconds"] = round(time.monotonic() - started, 3)
                try:
                    os.killpg(child.pid, 0)
                    record["group_gone"] = False
                except ProcessLookupError:
                    record["group_gone"] = True
                write_json(path, record)
                if not record["group_gone"]:
                    raise RuntimeError(f"owned process group {child.pid} survives")

    @staticmethod
    def reap(child):
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(child.pid, sig)
            except ProcessLookupError:
                break
            deadline = time.monotonic() + (10 if sig == signal.SIGTERM else 3)
            while time.monotonic() < deadline:
                try:
                    child.wait(timeout=0.02)
                except subprocess.TimeoutExpired:
                    pass
                try:
                    while os.waitpid(-child.pid, os.WNOHANG)[0]:
                        pass
                except ChildProcessError:
                    pass
                try:
                    os.killpg(child.pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.02)
        child.wait(timeout=5)


def copy_probe(owner, compose, env, name, item, destination):
    """Stream owned artifacts through exec; rootless daemon cp can reject RO binds."""
    owner.run(
        name,
        [
            *compose,
            "exec",
            "-T",
            "starlink-location",
            "timeout",
            "--kill-after=10s",
            "60s",
            "tar",
            "-C",
            "/probe",
            "-cf",
            "-",
            item,
        ],
        env=env,
        seconds=80,
    )
    destination = Path(destination)
    with tarfile.open(owner.evidence / (name + ".log")) as archive:
        members = archive.getmembers()
        for member in members:
            parts = Path(member.name).parts
            if (
                not parts
                or parts[0] != item
                or ".." in parts
                or Path(member.name).is_absolute()
                or not (member.isdir() or member.isfile())
            ):
                raise ValueError("unsafe container evidence archive")
        for member in members:
            relative = Path(*Path(member.name).parts[1:])
            target = (
                destination / relative
                if len(Path(member.name).parts) > 1
                else destination
            )
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as content:
                    target.write_bytes(content.read())


def fixture_cases(root):
    import copy

    folder = root / "backend/starlink-location/tests/fixtures/customer_briefing"
    result = {
        name: [json.loads((folder / f"{name.lower()}.json").read_text())]
        for name in ("F01", "F02", "F02_AR", "F03", "F04", "F05", "F06", "F09", "F10")
    }
    result["F08"] = json.loads((folder / "f08.json").read_text())["legs"]
    clocks = json.loads((folder / "f07.json").read_text())["cases"]
    from datetime import datetime

    for name, clock in zip(("midnight", "spring", "fall"), clocks, strict=True):
        data = copy.deepcopy(result["F01"][0])
        start, end = clock["takeoff"], clock["landing"]
        data["fixture"] = f"F07_{name}"
        data["mission"]["id"] = f"f07-{name}-mission"
        leg = data["mission"]["legs"][0]
        leg.update(id=f"f07-{name}", name=f"F07 {name}", adjusted_departure_time=start)
        data["utc_bounds"] = [start, end]
        route = data["route"]
        for point, instant in zip(route["points"], (start, end), strict=True):
            point["expected_arrival_time"] = instant
        route["timing_profile"].update(departure_time=start, arrival_time=end)
        data["timeline"]["mission_leg_id"] = leg["id"]
        data["timeline"]["segments"][0].update(start_time=start, end_time=end)
        for source in data["source_records"]:
            source.update(start_time=start, end_time=end)
        # Thirty-minute fixtures have contiguous standard 15-minute restrictions.
        from datetime import timedelta

        middle = (
            datetime.fromisoformat(start.replace("Z", "+00:00")) + timedelta(minutes=15)
        ).isoformat()
        template = copy.deepcopy(result["F01"][0]["resolved_restrictions"])
        for restriction, left, right in zip(
            template, (start, middle), (middle, end), strict=True
        ):
            restriction.update(start_time=left, end_time=right)
        data["resolved_restrictions"] = template
        data["expected"] = clock
        result[f"F07_{name}"] = [data]
    return result


def canonical_decks(root, output):
    """Controlled canonical snapshots, separately labeled from HTTP rebuild exports."""
    import copy
    import hashlib
    from unittest.mock import patch

    sys.path.insert(0, str(root / "backend/starlink-location"))
    from app.core.config import ConfigManager
    from app.mission.exporter.snapshot import ExportSnapshot
    from app.mission.exporter.snapshot_inputs import SourcePayload, canonical_json
    from app.mission.exporter.trial_projection import project_trial_leg
    from app.mission.package import __main__ as package
    from inspect_pptx import inspect
    from tests.unit.customer_briefing_fixtures import snapshot

    output.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name, cases in fixture_cases(root).items():
        cases = copy.deepcopy(cases)
        for case in cases:
            case["mission"]["legs"][0]["route_id"] = (
                case["mission"]["legs"][0]["id"] + "-route"
            )
        frozen_legs = tuple(snapshot(case) for case in cases)
        payloads = [
            SourcePayload("pois", b"[]"),
            SourcePayload("ground_entry", b"null"),
        ]
        for case in cases:
            route_id = case["mission"]["legs"][0]["route_id"]
            if case["route"]:
                payloads += [
                    SourcePayload("route/" + route_id, canonical_json(case["route"])),
                    SourcePayload("kml/" + route_id, kml(case["route"])),
                ]
        mission = dict(cases[0]["mission"])
        mission["legs"] = [case["mission"]["legs"][0] for case in cases]
        mission["name"] = f"Synthetic {name}"
        frozen = ExportSnapshot(
            mission["id"],
            hashlib.sha256(canonical_json(cases)).hexdigest(),
            canonical_json(mission),
            frozen_legs,
            tuple(payloads),
            (),
        )
        started = time.monotonic()
        with patch.object(package, "capture_export_snapshot", return_value=frozen):
            ConfigManager.get_instance().update_config(
                {"customer_briefing_trial_enabled": True}
            )
            result = package.export_mission_package_result(mission["id"], None, None)
        import zipfile

        with result.stream:
            content = result.stream.read()
        folder = output / name
        folder.mkdir()
        (folder / "mission.zip").write_bytes(content)
        with zipfile.ZipFile(__import__("io").BytesIO(content)) as archive:
            legacy = archive.read("exports/mission/mission-slides.pptx")
            trial = archive.read("exports/mission/mission-customer-briefing-trial.pptx")
            zip_manifest = json.loads(archive.read("manifest.json"))
        (folder / "legacy.pptx").write_bytes(legacy)
        (folder / "trial.pptx").write_bytes(trial)
        projected = tuple(project_trial_leg(leg) for leg in frozen_legs)
        report = {
            "basis": "canonical synthetic snapshot injected at capture boundary; not HTTP rebuild qualification",
            "snapshot_fingerprint": frozen.fingerprint,
            "zip_sha256": hashlib.sha256(content).hexdigest(),
            "manifest": zip_manifest,
            "warnings": result.warnings,
            "export_seconds": round(time.monotonic() - started, 3),
            "legs": [
                {
                    "id": leg.leg_id,
                    "windows": [
                        {
                            "id": i.id,
                            "number": i.window_number,
                            "start": i.start_time.isoformat(),
                            "end": i.end_time.isoformat(),
                            "posture": i.posture,
                            "remaining": i.remaining_transports,
                            "sources": i.active_source_ids,
                        }
                        for i in leg.coordination_rows
                    ],
                }
                for leg in projected
            ],
            "legacy": inspect(folder / "legacy.pptx"),
            "trial": inspect(folder / "trial.pptx", True),
        }
        write_json(folder / "inspection.json", report)
        manifest[name] = report
        print(f'{name}: paired decks, {report["export_seconds"]}s', flush=True)
    write_json(output / "decks.json", manifest)


def kml(route):
    from xml.sax.saxutils import escape

    points = route["points"]
    coordinates = " ".join(f'{p["longitude"]},{p["latitude"]},0' for p in points)
    markers = []
    for n, point in enumerate(points):
        stamp = (
            point.get("expected_arrival_time", "")
            .replace("T", " ")
            .replace("+00:00", "Z")
        )
        markers.append(
            f'<Placemark><name>WP{n}</name><description>Time Over Waypoint: {escape(stamp)}</description><Point><coordinates>{point["longitude"]},{point["latitude"]},0</coordinates></Point></Placemark>'
        )
    return (
        '<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Synthetic acceptance route</name><Placemark><LineString><coordinates>'
        + coordinates
        + "</coordinates></LineString></Placemark>"
        + "".join(markers)
        + "</Document></kml>"
    ).encode()


def import_archives(root, output):
    import copy
    import zipfile

    output.mkdir()
    result = {}
    for name, cases in fixture_cases(root).items():
        mission = copy.deepcopy(cases[0]["mission"])
        mission["name"] = f"Synthetic {name}"
        mission["legs"] = []
        path = output / f"{name}.zip"
        with zipfile.ZipFile(path, "w") as archive:
            for case in cases:
                leg = copy.deepcopy(case["mission"]["legs"][0])
                leg["route_id"] = f'{leg["id"]}-route'
                mission["legs"].append(leg)
                if case["route"]:
                    archive.writestr(
                        f'routes/{leg["route_id"]}.kml', kml(case["route"])
                    )
                archive.writestr(f'legs/{leg["id"]}.json', json.dumps(leg))
                archive.writestr(
                    f'pois/{leg["id"]}-pois.json',
                    json.dumps(
                        {
                            "pois": [
                                {
                                    "id": f'{leg["id"]}-customer-marker',
                                    "name": "Synthetic retained source POI",
                                    "category": "mission-event",
                                    "mission_id": mission["id"],
                                    "route_id": leg["route_id"],
                                    "latitude": 0.1,
                                    "longitude": 0.0,
                                    "created_at": "2026-10-07T08:00:00Z",
                                    "updated_at": "2026-10-07T08:00:00Z",
                                }
                            ]
                        }
                    ),
                )
            archive.writestr("mission.json", json.dumps(mission))
        result[name] = {
            "mission_id": mission["id"],
            "archive": str(path),
            "mission": mission,
        }
    write_json(output / "imports.json", result)
    return result


def http(base, path, *, data=None, headers=None):
    from urllib.error import HTTPError
    from urllib.request import ProxyHandler, Request, build_opener

    # Private loopback acceptance API never travels through a remote proxy.
    opener = build_opener(ProxyHandler({}))
    for attempt in range(4):
        try:
            with opener.open(
                Request(base + path, data=data, headers=headers or {}), timeout=180
            ) as response:
                return response.read(), dict(response.headers)
        except HTTPError as error:
            if error.code != 429 or attempt == 3:
                raise
            time.sleep(61)
    raise AssertionError("unreachable")


def upload(base, path):
    boundary = "customer-briefing-fixed-boundary"
    payload = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="mission.zip"\r\nContent-Type: application/zip\r\n\r\n'.encode()
        + path.read_bytes()
        + f"\r\n--{boundary}--\r\n".encode()
    )
    content, _ = http(
        base,
        "/api/v2/missions/import",
        data=payload,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    result = json.loads(content)
    if result.get("success") is not True:
        raise ValueError("normal source import failed")
    return result


def api_exports(base, imports, output, status):
    import hashlib
    import io
    import zipfile

    output.mkdir()
    report = {}
    for name, entry in imports.items():
        before, _ = http(base, f'/api/v2/missions/{entry["mission_id"]}')
        folder = output / name
        folder.mkdir()
        (folder / "mission-before.json").write_bytes(before)
        started = time.monotonic()
        data, headers = http(
            base,
            f'/api/v2/missions/{entry["mission_id"]}/export',
            data=b"{}",
            headers={
                "Content-Type": "application/json",
                "Origin": base,
            },
        )
        elapsed = time.monotonic() - started
        lowered = {key.lower(): value for key, value in headers.items()}
        actual = lowered.get("x-mission-export-trial-status")
        if actual != status:
            raise ValueError(f"{name}: trial status {actual!r}, expected {status!r}")
        warnings = json.loads(lowered["x-mission-export-warnings"])
        if len(lowered["x-mission-export-warnings"]) > 2048 or any(
            "private-token" in w or "/private" in w for w in warnings
        ):
            raise ValueError("unsafe export warnings")
        (folder / "mission.zip").write_bytes(data)
        with zipfile.ZipFile(io.BytesIO(data)) as archive, zipfile.ZipFile(
            entry["archive"]
        ) as source:
            assert archive.testzip() is None
            manifest = json.loads(archive.read("manifest.json"))
            trial = "exports/mission/mission-customer-briefing-trial.pptx"
            assert (trial in archive.namelist()) == (status == "included")
            assert "exports/mission/mission-slides.pptx" in archive.namelist()
            for leg in entry["mission"]["legs"]:
                exported = json.loads(archive.read(f'legs/{leg["id"]}.json'))
                assert source_transport_equal(
                    exported["transports"],
                    next(
                        item["transports"]
                        for item in json.loads(before)["legs"]
                        if item["id"] == leg["id"]
                    ),
                ), "saved transport model changed during export"
                path = f'routes/{leg["route_id"]}.kml'
                if path in source.namelist():
                    assert archive.read(path) == source.read(path)
                pois = json.loads(archive.read(f'pois/{leg["id"]}-pois.json'))["pois"]
                source_pois_path = f'pois/{leg["id"]}-pois.json'
                expected_pois = (
                    json.loads(source.read(source_pois_path)).get("pois", [])
                    if source_pois_path in source.namelist()
                    else []
                )
                for expected in expected_pois:
                    # Normal import allocates persistent IDs and timestamps.
                    # Saved labels, coordinates and categories remain source facts.
                    assert any(
                        all(
                            p.get(k) == expected.get(k)
                            for k in ("name", "latitude", "longitude", "category")
                        )
                        for p in pois
                    ), "source POI changed or missing"
                sentinel = entry.get(
                    "required_poi_name", "Synthetic retained source POI"
                )
                if sentinel:
                    assert any(
                        p["name"] == sentinel for p in pois
                    ), "synthetic source POI missing"
            for path, label in (
                ("exports/mission/mission-slides.pptx", "legacy"),
                (trial, "trial"),
            ):
                if path in archive.namelist():
                    (folder / f"{label}.pptx").write_bytes(archive.read(path))
        from inspect_pptx import inspect

        deck_inspection = {
            p.stem: inspect(p, p.stem == "trial") for p in folder.glob("*.pptx")
        }
        write_json(folder / "inspection.json", deck_inspection)
        after, _ = http(base, f'/api/v2/missions/{entry["mission_id"]}')
        assert before == after, "export wrote mission metadata"
        assert status != "failed" or warnings
        report[name] = {
            "status": actual,
            "warnings": warnings,
            "seconds": round(elapsed, 3),
            "headers": lowered,
            "manifest": manifest,
            "zip_sha256": hashlib.sha256(data).hexdigest(),
            "source_preservation": "pass",
            "mission_before_after_equal": True,
        }
        write_json(folder / "api.json", report[name])
    write_json(output / "exports.json", report)
    return report


def browser_journey(owner, profile_path, task, base, output, mission_name, status):
    sys.path.insert(0, str(ROOT))
    from tools.acceptance.platform.health import (
        PlatformHealthExecutor,
        start_final_browser_session,
    )
    from tools.acceptance.platform.runner import _load_profile, _probe

    output.mkdir()
    write_json(
        output / "ownership.json",
        {
            "profile": str(profile_path),
            "task_root": str(task),
            "handles": "platform health session owns browser/Xvfb/CDP/profile; closes in finally",
        },
    )
    session = start_final_browser_session(
        _load_profile(profile_path), task, PlatformHealthExecutor(probe=_probe)
    )
    try:
        write_json(
            output / "session.json",
            {
                "cdp": session.cdp_url,
                "browser_pid": session._browser.pid,
                "browser_pgid": session._browser_group,
                "xvfb_pid": session._xvfb.pid,
                "display": session.display,
                "metrics": session.metrics,
                "webgl2": session.webgl2,
            },
        )
        owner.run(
            output.name,
            [
                "node",
                str(HERE / "journey.mjs"),
                session.cdp_url,
                base,
                str(output),
                mission_name,
                status,
            ],
            seconds=240,
        )
    finally:
        session.close()
        for name, content in session.artifacts.items():
            (output / name).write_bytes(content)
        write_json(output / "cleanup.json", {"closed": True})


def source_transport_equal(left, right):
    sys.path.insert(0, str(ROOT / "backend/starlink-location"))
    from app.mission.models import TransportConfig

    return TransportConfig.model_validate(left) == TransportConfig.model_validate(right)


def scoped_docker(owner, project, kind, serial):
    command = (
        ["docker", "ps", "-aq"]
        if kind == "containers"
        else ["docker", kind[:-1], "ls", "-q"]
    )
    name = f"{serial}-{kind}"
    owner.run(
        name,
        [*command, "--filter", f"label=com.docker.compose.project={project}"],
        seconds=30,
    )
    return (owner.evidence / f"{name}.log").read_text().strip().splitlines()


def port_free(port):
    import socket

    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", port))


def production(args):

    validate_candidate(ROOT, args.sha)
    project = "starlink-dashboard-customer-briefing-" + args.sha[:12]
    port_free(args.port)
    evidence, task = args.evidence.resolve(), args.task_root.resolve()
    if args.check:
        print(f"Clean candidate {args.sha}; loopback port {args.port} available.")
        return 0
    claim_paths(evidence, task)
    owner = Owner(evidence)
    resources = {
        "project": project,
        "candidate": args.sha,
        "runner_pid": os.getpid(),
        "runner_pgid": os.getpgrp(),
        "ports": [args.port],
        "source": str(task / "source"),
        "containers": [],
        "images": [
            f"{project}-backend:{args.sha}",
            f"{project}-frontend:{args.sha}",
            f"{project}-render:{args.sha}",
        ],
        "private_volumes": [
            project + "_" + v
            for v in (
                "probe",
                "missions",
                "settings",
                "satellites",
                "coverage",
                "routes",
                "simulation-routes",
                "pois",
                "metrics",
            )
        ],
    }
    write_json(evidence / "resources.json", resources)
    started = False
    claimed_project = False
    owned_images = []
    render_name = project + "-render"
    report = {
        "candidate": args.sha,
        "status": "incomplete",
        "customer_acceptance": "pending explicit customer layout/semantics acceptance",
        "desktop_powerpoint": "pending offline edit of table/title in desktop PowerPoint",
        "browser": "pending provisioned platform descriptor",
        "rollout": "default off; no promotion, legacy replacement, merge or phase two",
    }
    env = {
        **os.environ,
        "ACCEPTANCE_CANDIDATE_SHA": args.sha,
        "BRIEFING_PROJECT": project,
        "BRIEFING_SOURCE": str(task / "source"),
        "BRIEFING_ENABLED": "true",
        "BRIEFING_FAULT": "none",
        "BRIEFING_PORT": str(args.port),
    }
    compose = ["docker", "compose", "-p", project, "-f", str(HERE / "compose.yml")]
    try:
        for kind in ("containers", "networks", "volumes"):
            if scoped_docker(owner, project, kind, "preflight"):
                raise ValueError(f"existing project {kind}; refusing ownership")
        for index, tag in enumerate(resources["images"]):
            owner.run(
                f"preflight-image-{index}",
                ["docker", "image", "ls", "-q", tag],
                seconds=30,
            )
            if (evidence / f"preflight-image-{index}.log").read_text().strip():
                raise ValueError("existing image tag; refusing ownership")
        claimed_project = True
        owned_images = resources["images"]
        source = task / "source"
        source.mkdir()
        owner.run(
            "source-archive",
            ["git", "archive", args.sha, "--output", str(task / "source.tar")],
            cwd=ROOT,
            seconds=30,
        )
        owner.run(
            "source-extract",
            ["tar", "-xf", str(task / "source.tar"), "-C", str(source)],
            seconds=30,
        )
        # Compose references the archived configuration and build context only.
        compose[-1] = str(source / "tools/acceptance/customer-briefing/compose.yml")
        owner.run(
            "docker-runtime",
            ["docker", "info", "--format", "{{.ServerVersion}} {{.Driver}}"],
            seconds=30,
        )
        owner.run("docker-context", ["docker", "context", "show"], seconds=30)
        (evidence / "docker-endpoint.txt").write_text(
            os.environ.get("DOCKER_HOST", "<active context>") + "\n"
        )
        owner.run(
            "compose-config", [*compose, "config", "--quiet"], env=env, seconds=30
        )
        owner.run("build", [*compose, "build", "--no-cache"], env=env, seconds=2700)
        started = True
        owner.run(
            "start",
            [
                *compose,
                "up",
                "--no-build",
                "--detach",
                "--wait",
                "--wait-timeout",
                "180",
            ],
            env=env,
            seconds=240,
        )
        owner.run(
            "image-identities",
            ["docker", "image", "inspect", *resources["images"][:2]],
            seconds=30,
        )
        identities = json.loads((evidence / "image-identities.log").read_text())
        assert all(
            i["Config"]["Labels"]["org.opencontainers.image.revision"] == args.sha
            for i in identities
        )
        base = f"http://127.0.0.1:{args.port}"
        http(base, "/missions")
        http(base, "/api/status")
        imports = import_archives(source, evidence / "imports")
        if getattr(args, "existing_package", None):
            from anonymize_package import anonymize

            existing_path = evidence / "imports/existing.zip"
            existing_info = anonymize(args.existing_package, existing_path)
            import zipfile

            with zipfile.ZipFile(existing_path) as archive:
                existing_mission = json.loads(archive.read("mission.json"))
            imports["EXISTING"] = {
                "archive": str(existing_path),
                "mission_id": existing_mission["id"],
                "mission": existing_mission,
                "required_poi_name": None,
            }
            write_json(evidence / "existing-selection.json", existing_info)
        write_json(evidence / "imports/imports.json", imports)
        imported = {}
        for name, entry in imports.items():
            imported[name] = upload(base, Path(entry["archive"]))
            write_json(evidence / "import-results.json", imported)
        api_exports(base, imports, evidence / "enabled", "included")
        # Re-import one actual enabled package using the unchanged import route.
        replay = upload(base, evidence / "enabled/F02_AR/mission.zip")
        assert (
            replay["success"]
            and replay["mission_id"] == imports["F02_AR"]["mission_id"]
        )
        write_json(evidence / "round-trip.json", replay)
        if args.profile and not args.api_only:
            browser_journey(
                owner,
                args.profile,
                task / "browser-enabled",
                base,
                evidence / "ui-enabled",
                "Synthetic F02_AR",
                "included",
            )
            report["browser"] = "enabled UI passed; remaining modes pending"
        owner.run(
            "fixture-expectations",
            [
                *compose,
                "exec",
                "-T",
                "starlink-location",
                "timeout",
                "--kill-after=10s",
                "5m",
                "env",
                "PYTHONPATH=/app:/source/backend/starlink-location",
                "python",
                "-m",
                "pytest",
                "-q",
                "/source/backend/starlink-location/tests/unit/test_trial_projection.py",
                "/source/backend/starlink-location/tests/unit/test_trial_clocks.py",
                "--basetemp",
                "/probe/fixture-temp",
            ],
            env=env,
            seconds=320,
        )
        owner.run(
            "canonical",
            [
                *compose,
                "exec",
                "-T",
                "starlink-location",
                "timeout",
                "--kill-after=10s",
                "10m",
                "python",
                "/acceptance/generate.py",
                "--canonical",
                "/source",
                "/probe/canonical",
            ],
            env=env,
            seconds=620,
        )
        copy_probe(
            owner, compose, env, "canonical-copy", "canonical", evidence / "canonical"
        )
        owner.run(
            "direct-legacy",
            [
                *compose,
                "exec",
                "-T",
                "starlink-location",
                "timeout",
                "--kill-after=10s",
                "3m",
                "python",
                "/acceptance/direct_export.py",
            ],
            env=env,
            seconds=200,
        )
        copy_probe(owner, compose, env, "direct-copy", "direct", evidence / "direct")
        env["BRIEFING_ENABLED"] = "false"
        owner.run(
            "disable",
            [
                *compose,
                "up",
                "--no-build",
                "--detach",
                "--wait",
                "--wait-timeout",
                "180",
                "starlink-location",
            ],
            env=env,
            seconds=240,
        )
        api_exports(base, imports, evidence / "disabled", "disabled")
        if args.profile and not args.api_only:
            browser_journey(
                owner,
                args.profile,
                task / "browser-disabled",
                base,
                evidence / "ui-disabled",
                "Synthetic F02_AR",
                "disabled",
            )
        env["BRIEFING_ENABLED"] = "true"
        faults = {}
        for fault in (
            "projection",
            "invalid-pptx",
            "browser",
            "texture",
            "deadline",
            "all-maps",
            "slow",
        ):
            env["BRIEFING_FAULT"] = fault
            owner.run(
                f"start-{fault}",
                [
                    *compose,
                    "up",
                    "--no-build",
                    "--detach",
                    "--wait",
                    "--wait-timeout",
                    "180",
                    "starlink-location",
                ],
                env=env,
                seconds=240,
            )
            status = "failed" if fault in ("projection", "invalid-pptx") else "included"
            faults[fault] = api_exports(
                base, {"F02_AR": imports["F02_AR"]}, evidence / f"fault-{fault}", status
            )
            if (
                args.profile
                and not args.api_only
                and fault in ("projection", "browser")
            ):
                browser_journey(
                    owner,
                    args.profile,
                    task / f"browser-{fault}",
                    base,
                    evidence / f"ui-{fault}",
                    "Synthetic F02_AR",
                    status,
                )
        report["faults"] = faults
        copy_probe(
            owner, compose, env, "probe-copy", "stages.jsonl", evidence / "stages.jsonl"
        )
        stages = [
            json.loads(line)
            for line in (evidence / "stages.jsonl").read_text().splitlines()
        ]
        primary = [
            m
            for stage in stages
            if stage.get("fault") == "none"
            for m in stage.get("maps", [])
            if m["status"] == "primary"
        ]
        assert any(
            m["leg_id"] == "f01" for m in primary
        ), "production default renderer never produced a primary F01 map"
        report["production_primary_maps"] = [
            {"leg_id": m["leg_id"], "views": m["views"]} for m in primary
        ]
        # Render representative paired extracts, retaining every remaining deck for inspection.
        owner.run(
            "container-logs-final",
            [*compose, "logs", "--no-color"],
            env=env,
            seconds=30,
        )
        owner.run(
            "api-stop",
            [*compose, "down", "--volumes", "--remove-orphans"],
            env=env,
            seconds=120,
        )
        started = False

        review = evidence / "review"
        review.mkdir()
        for basis, names in (
            (
                "canonical",
                (
                    "F01",
                    "F02_AR",
                    "F03",
                    "F06",
                    "F07_midnight",
                    "F07_spring",
                    "F07_fall",
                    "F08",
                    "F09",
                    "F10",
                ),
            ),
            ("enabled", ("F01", "F02_AR", "F08", "F10")),
            ("fault-browser", ("F02_AR",)),
            ("fault-all-maps", ("F02_AR",)),
        ):
            for name in names:
                src = evidence / basis / name
                dest = review / f"{basis}-{name}"
                dest.mkdir()
                for path in src.glob("*.pptx"):
                    shutil.copy2(path, dest / path.name)
                if (src / "inspection.json").exists():
                    shutil.copy2(src / "inspection.json", dest / "inspection.json")
        if "EXISTING" in imports:
            dest = review / "enabled-EXISTING"
            dest.mkdir()
            for path in (evidence / "enabled/EXISTING").glob("*.pptx"):
                shutil.copy2(path, dest / path.name)
        render_image = resources["images"][2]
        owner.run(
            "render-build",
            [
                "docker",
                "build",
                "-t",
                render_image,
                "-f",
                str(source / "tools/acceptance/customer-briefing/Dockerfile.render"),
                str(source / "tools/acceptance/customer-briefing"),
            ],
            seconds=900,
        )
        owner.run(
            "render-image", ["docker", "image", "inspect", render_image], seconds=30
        )
        owner.run(
            "render",
            [
                "docker",
                "run",
                "--rm",
                "--init",
                "--name",
                render_name,
                "--label",
                f"com.docker.compose.project={project}",
                "--network",
                "none",
                "--read-only",
                "--tmpfs",
                "/tmp:rw,mode=1777",
                "--mount",
                f"type=bind,src={review},dst=/evidence",
                "--mount",
                f"type=bind,src={source}/tools/acceptance/customer-briefing,dst=/acceptance,readonly",
                render_image,
                "python3",
                "/acceptance/render_decks.py",
                "/evidence",
            ],
            seconds=1200,
        )
        report["automated_api"] = "passed"
        report["canonical_pairs"] = (
            "passed; canonical fixture capture boundary clearly labeled"
        )
        report["rendered"] = (
            "passed offline LibreOffice; visual review remains separately recorded"
        )
        if args.profile and not args.api_only:
            report["browser"] = (
                "passed enabled, disabled, failure warning and fallback UI"
            )
            report["status"] = "automated gates passed; customer review pending"
        else:
            report["browser"] = (
                "environment_blocked: no provisioned platform-browser descriptor; UI journey not run"
            )
        write_json(evidence / "report.json", report)
    finally:
        cleanup = {
            "containers": [],
            "networks": [],
            "volumes": [],
            "listeners": [],
            "errors": [],
        }

        def attempt(action):
            try:
                return action()
            except (
                OSError,
                subprocess.SubprocessError,
                ValueError,
                RuntimeError,
                KeyboardInterrupt,
                SystemExit,
            ) as error:
                cleanup["errors"].append(str(error))
                return None

        if started:
            if not (evidence / "stages.jsonl").exists():
                try:
                    copy_probe(
                        owner,
                        compose,
                        env,
                        "probe-copy-on-exit",
                        "stages.jsonl",
                        evidence / "stages-on-exit.jsonl",
                    )
                except (
                    OSError,
                    ValueError,
                    tarfile.TarError,
                    subprocess.SubprocessError,
                ) as exc:
                    report.setdefault("evidence_errors", []).append(str(exc))
            attempt(
                lambda: owner.run(
                    "container-logs",
                    [*compose, "logs", "--no-color"],
                    env=env,
                    seconds=30,
                )
            )
        if claimed_project:
            attempt(
                lambda: owner.run(
                    "render-presence",
                    ["docker", "ps", "-aq", "--filter", f"name=^/{render_name}$"],
                    seconds=30,
                )
            )
            presence = evidence / "render-presence.log"
            if presence.exists() and presence.read_text().strip():
                attempt(
                    lambda: owner.run(
                        "render-stop",
                        ["docker", "stop", "--time", "10", render_name],
                        seconds=25,
                    )
                )
                attempt(
                    lambda: owner.run(
                        "render-remove", ["docker", "rm", render_name], seconds=30
                    )
                )
        if started:
            attempt(
                lambda: owner.run(
                    "down",
                    [*compose, "down", "--volumes", "--remove-orphans"],
                    env=env,
                    seconds=120,
                )
            )
        if claimed_project:
            for kind in ("containers", "networks", "volumes"):
                found = attempt(
                    lambda kind=kind: scoped_docker(owner, project, kind, "final")
                )
                cleanup[kind] = found if found is not None else ["inspection failed"]
        attempt(lambda: port_free(args.port))
        for tag in owned_images:
            label = tag.split("-")[-1].split(":")[0]
            attempt(
                lambda tag=tag, label=label: owner.run(
                    "image-check-" + label,
                    ["docker", "image", "ls", "-q", tag],
                    seconds=30,
                )
            )
            check = evidence / ("image-check-" + label + ".log")
            if check.exists() and check.read_text().strip():
                attempt(
                    lambda tag=tag, label=label: owner.run(
                        "image-remove-" + label,
                        ["docker", "image", "rm", tag],
                        seconds=30,
                    )
                )
        # Keep an archived source/configuration if Docker teardown is incomplete.
        if (
            not any(cleanup[k] for k in ("containers", "networks", "volumes"))
            and task.exists()
        ):
            attempt(lambda: shutil.rmtree(task))
        write_json(evidence / "cleanup.json", cleanup)
        report["cleanup"] = cleanup
        write_json(evidence / "report.json", report)
        if cleanup["errors"] or any(
            cleanup[k] for k in ("containers", "networks", "volumes", "listeners")
        ):
            raise RuntimeError(f"cleanup incomplete: {cleanup}")
    return 0 if args.api_only or report["browser"].startswith("passed") else 3


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "--canonical":
        canonical_decks(Path(sys.argv[2]), Path(sys.argv[3]))
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--task-root", required=True, type=Path)
    parser.add_argument("--profile", type=Path)
    parser.add_argument(
        "--existing-package",
        type=Path,
        help="existing local package; anonymized locally, never committed",
    )
    parser.add_argument("--port", type=int, default=15309)
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--api-only",
        action="store_true",
        help="diagnostic only; explicitly records UI acceptance as blocked",
    )
    args = parser.parse_args()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(
            sig, lambda signum, frame: (_ for _ in ()).throw(SystemExit(128 + signum))
        )
    return production(args)


if __name__ == "__main__":
    sys.exit(main())
