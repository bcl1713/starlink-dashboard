"""Real source capture and ZIP downloads through production Nginx."""

import csv
import io
import json
import time
import zipfile
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

PDF = "exports/mission/mission-customer-briefing-trial.pdf"
EVIDENCE = "exports/mission/mission-customer-briefing-evidence.json"
WARNINGS = {
    "snapshot",
    "data",
    "page-budget",
    "overflow",
    "runtime",
    "deadline",
    "pdf",
    "evidence",
    "cleanup",
    "publication",
    "busy",
}


def compare_legacy(disabled, enabled):
    """Compare every legacy entry and PPTX member; ignore ZIP container times."""

    def members(content):
        result = {}
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            for name in archive.namelist():
                if name in {PDF, EVIDENCE, "manifest.json"}:
                    continue
                value = archive.read(name)
                if name.endswith(".pptx"):
                    with zipfile.ZipFile(io.BytesIO(value)) as presentation:
                        for member in presentation.namelist():
                            result[name + "::" + member] = presentation.read(member)
                    continue
                if name.startswith("exports/mission/") and name.endswith(".csv"):
                    rows = list(csv.reader(io.StringIO(value.decode())))
                    if rows and len(rows[0]) == 6 and rows[0][4] == "Generated":
                        rows[0][5] = "identified-generation-clock"
                        output = io.StringIO(newline="")
                        csv.writer(output).writerows(rows)
                        value = output.getvalue().encode()
                result[name] = value
        return result

    left, right = members(disabled), members(enabled)
    differences = sorted(
        name for name in left.keys() | right.keys() if left.get(name) != right.get(name)
    )
    if differences:
        raise ValueError("Legacy content differs: " + ", ".join(differences))
    return {
        "matched": True,
        "memberHashes": {
            name: sha256(content).hexdigest() for name, content in left.items()
        },
        "exclusions": [
            "ZIP member container timestamps",
            "combined mission CSV Generated clock",
            "manifest separately qualified; optional pair added",
        ],
    }


def inspect_download(content, headers, expected_status):
    headers = {key.lower(): value for key, value in headers.items()}
    status = headers.get("x-customer-briefing-status")
    if status != (None if expected_status == "disabled" else expected_status):
        raise ValueError(
            f"Unexpected customer briefing response status: expected={expected_status}, actual={status}, warning={headers.get('x-customer-briefing-warning')}"
        )
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = archive.namelist()
        manifest = json.loads(archive.read("manifest.json"))
        structure = manifest["file_structure"]
        listed = [name for group in structure.values() for name in group]
        stats = manifest["statistics"]
        if (
            manifest["version"] != "2.0"
            or len(listed) != stats["total_files"]
            or len(structure["mission_exports"]) != stats["mission_export_files"]
            or any(name not in names for name in listed)
        ):
            raise ValueError("Manifest file/statistics mismatch")
        included = PDF in names and EVIDENCE in names
        if any(name in names for name in (PDF, EVIDENCE)) != included:
            raise ValueError("Partial optional artifact pair")
        if (
            included != (status == "included")
            or any(name in listed for name in (PDF, EVIDENCE)) != included
        ):
            raise ValueError("Optional artifact/manifest/status mismatch")
        if not any(name.endswith(".pptx") for name in names):
            raise ValueError("Legacy presentation missing")
        warning = headers.get("x-customer-briefing-warning")
        if (status == "omitted" and warning not in WARNINGS) or (
            status != "omitted" and warning
        ):
            raise ValueError("Unsafe or unexpected warning header")
        result = {
            "status": expected_status,
            "warning": warning,
            "members": names,
            "manifest": manifest,
            "zipSha256": sha256(content).hexdigest(),
        }
        if included:
            evidence = json.loads(archive.read(EVIDENCE))
            render = evidence["render"]
            rows = [
                (leg["legId"], row["id"])
                for leg in evidence["legs"]
                for row in leg["customerRows"]
            ]
            proof = render["pdfValidation"]
            if (
                evidence["schemaVersion"] != 2
                or evidence["missionId"] != manifest["mission_id"]
                or render["status"] != "success"
                or render["cleanup"]["success"] is not True
                or not 0 <= render["totalMs"] <= 60000
                or render["launchCount"] != 1
                or render["sharedBrowser"] is not True
                or proof["verified"] is not True
                or [(row["legId"], row["rowId"]) for row in proof["rows"]] != rows
                or any(
                    not row["cellsMatched"] or not row["inBounds"]
                    for row in proof["rows"]
                )
                or sha256(archive.read(PDF)).hexdigest()
                != render["artifactHashes"]["pdfPath"]
            ):
                raise ValueError("Unqualified PDF/evidence pair")
            for leg in evidence["legs"]:
                if (
                    leg["mapInputDiagnostics"]
                    != render["maps"][leg["legId"]]["inputDiagnostics"]
                ):
                    raise ValueError("Map input diagnostic reasons lost")
            result.update(
                pageCount=proof["pageCount"], rowCount=len(rows), evidence=evidence
            )
        return result


class ProductionApi:
    def __init__(self, owner):
        self.owner = owner
        self.origin = f"http://127.0.0.1:{owner.env['BRIEFING_PORT']}"
        # Only loopback requests bypass proxies; external build/source access does not.
        self.opener = build_opener(ProxyHandler({}))

    def request(self, method, path, *, data=None, multipart=None, timeout=95):
        headers = {}
        body = None
        if data is not None:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
        if multipart:
            filename, body = multipart
            boundary = "briefing-production-owned-upload"
            body = (
                f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()
                + body
                + f"\r\n--{boundary}--\r\n".encode()
            )
            headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        for attempt in range(3):
            if self.owner.cancelled:
                raise InterruptedError("Production request cancelled")
            started = time.monotonic()
            try:
                with self.opener.open(
                    Request(
                        self.origin + path, data=body, headers=headers, method=method
                    ),
                    timeout=timeout,
                ) as response:
                    return (
                        response.read(),
                        dict(response.headers),
                        time.monotonic() - started,
                    )
            except HTTPError as error:
                if error.code != 429 or attempt == 2:
                    detail = error.read().decode(errors="replace")
                    raise RuntimeError(
                        f"{method} {path}: HTTP {error.code}: {detail}"
                    ) from error
                # Respect the real application's limiter without disabling it.
                time.sleep(min(60, max(1, int(error.headers.get("Retry-After", "60")))))
        raise RuntimeError("Request retries exhausted")


def qualify(owner):
    from production_seed import provider_seed, seed_missions

    owner.compose(
        "run",
        "--rm",
        "--no-deps",
        "starlink-location",
        "python",
        "-c",
        provider_seed(),
        timeout=30,
    )
    owner.compose("up", "-d", "--wait", "--wait-timeout", "150", timeout=180)
    api = ProductionApi(owner)
    fixtures = seed_missions(api, owner.root)
    reports = []
    tools = (
        Path(owner.env["BRIEFING_SOURCE_ROOT"]) / "tools/acceptance/customer-briefing"
    )

    def copy_to_backend(source, destination):
        owner.compose("cp", str(source), f"starlink-location:{destination}", timeout=30)

    def backend_python(code, *arguments, timeout=30):
        return owner.compose(
            "exec",
            "-T",
            "--user",
            "appuser",
            "starlink-location",
            "python",
            "-c",
            code,
            *arguments,
            timeout=timeout,
        )

    audit_code = (tools / "production_runtime_audit.py").read_text()
    audit_reports = []

    def audit(label, baseline=None):
        result = json.loads(backend_python(audit_code).splitlines()[-1])
        if baseline is not None and result["sourceHashes"] != baseline["sourceHashes"]:
            raise ValueError("Export changed persisted inputs: " + label)
        result["label"] = label
        audit_reports.append(result)
        (owner.root / "runtime-audits.json").write_text(
            json.dumps(audit_reports, indent=2)
        )
        return result

    def browser(case, status):
        baseline = audit("before-browser-" + case + "-" + status)
        script = "/tmp/briefing-production-journey.mjs"
        copy_to_backend(tools / "production-journey.mjs", script)
        output = f"/tmp/briefing-browser-{case}-{status}"
        result = json.loads(
            owner.compose(
                "exec",
                "-T",
                "--user",
                "appuser",
                "starlink-location",
                "node",
                script,
                "http://mission-planner",
                fixtures[case]["name"],
                status,
                output,
                timeout=110,
            ).splitlines()[-1]
        )
        destination = owner.root / "browser" / f"{case}-{status}"
        destination.mkdir(parents=True)
        owner.compose(
            "cp", f"starlink-location:{output}/.", str(destination), timeout=30
        )
        content = (destination / "download.zip").read_bytes()
        headers = result["requests"][0]["headers"]
        inspect_download(content, headers, status)
        audit("after-browser-" + case + "-" + status, baseline)
        return result

    def pdf_inspection(destination, label):
        archive = f"/tmp/briefing-production-{label}.zip"
        output = f"/tmp/briefing-pdf-{label}"
        copy_to_backend(destination / "download.zip", archive)
        probe = (tools / "production_pdf_probe.py").read_text()
        # python -c preserves arguments; no shell interpolation or endpoint replacement.
        result = json.loads(
            owner.compose(
                "exec",
                "-T",
                "--user",
                "appuser",
                "starlink-location",
                "python",
                "-c",
                probe,
                archive,
                output,
                timeout=180,
            ).splitlines()[-1]
        )
        target = destination / "actual-pdf"
        target.mkdir()
        owner.compose("cp", f"starlink-location:{output}/.", str(target), timeout=30)
        owner.compose(
            "exec",
            "-T",
            "--user",
            "appuser",
            "starlink-location",
            "python",
            "-c",
            "import shutil,sys; from pathlib import Path; shutil.rmtree(sys.argv[1]); Path(sys.argv[2]).unlink()",
            output,
            archive,
            timeout=30,
        )
        return result

    def download(case, status, attempt=None, warning=None):
        baseline = audit("before-download-" + (attempt or case))
        mission = fixtures[case]["id"]
        label = attempt or case
        content, headers, elapsed = api.request(
            "POST", f"/api/v2/missions/{mission}/export"
        )
        destination = owner.root / "downloads" / label
        destination.mkdir(parents=True)
        (destination / "download.zip").write_bytes(content)
        (destination / "response.json").write_text(
            json.dumps({"headers": headers, "proxyTotalSeconds": elapsed}, indent=2)
        )
        report = inspect_download(content, headers, status)
        if warning is not None and report["warning"] != warning:
            raise ValueError("Unexpected omission boundary: " + str(report["warning"]))
        report.update(case=case, attempt=label, proxyTotalSeconds=elapsed)
        if status == "included":
            report["actualPdfInspection"] = pdf_inspection(destination, label)
        (destination / "inspection.json").write_text(json.dumps(report, indent=2))
        reports.append(report)
        (owner.root / "production-downloads.json").write_text(
            json.dumps(reports, indent=2)
        )
        audit("after-download-" + label, baseline)
        return report

    download("normal", "disabled", "normal-disabled")
    browser_reports = [browser("normal", "disabled")]
    owner.env["BRIEFING_ENABLED"] = "true"
    owner.compose(
        "up",
        "-d",
        "--force-recreate",
        "--no-deps",
        "--wait",
        "--wait-timeout",
        "150",
        "starlink-location",
        timeout=180,
    )
    # Nginx resolves upstream addresses at startup; recreate its real image too.
    owner.compose(
        "up", "-d", "--force-recreate", "--no-deps", "mission-planner", timeout=60
    )
    observer = "/tmp/briefing-production-observer.py"
    copy_to_backend(tools / "production_observer.py", observer)
    owner.ownership["observer"] = {
        "service": "starlink-location",
        "script": observer,
        "output": "/tmp/briefing-production-observations",
    }
    owner.persist()
    owner.compose(
        "exec",
        "-d",
        "-T",
        "--user",
        "appuser",
        "starlink-location",
        "python",
        observer,
        timeout=30,
    )
    # Supported storage cases retain the real saved inputs and cached predictions.
    backend_python(
        "from app.mission.storage import delete_mission_timeline; "
        "delete_mission_timeline('briefing-missing-timeline-leg-1', 'briefing-missing-timeline')"
    )
    backend_python(
        "from pathlib import Path; "
        "Path('/data/routes/briefing-cached-missing-route-route-1.kml').unlink()"
    )
    # Let the real RouteManager filesystem watcher observe the removed input.
    time.sleep(2)
    for case in fixtures:
        download(
            case,
            (
                "omitted"
                if case in {"over-budget", "cached-missing-route"}
                else "included"
            ),
        )
    legacy_comparison = compare_legacy(
        (owner.root / "downloads/normal-disabled/download.zip").read_bytes(),
        (owner.root / "downloads/normal/download.zip").read_bytes(),
    )
    (owner.root / "legacy-comparison.json").write_text(
        json.dumps(legacy_comparison, indent=2)
    )
    for attempt in (2, 3):
        download("five-leg", "included", f"five-leg-cold-{attempt}")
    five = [r for r in reports if r["case"] == "five-leg"]
    keys = ("normalizedPdfHash", "geometryTextHash", "rasters", "snapshotFingerprint")
    if any(
        any(
            r["actualPdfInspection"][key] != five[0]["actualPdfInspection"][key]
            for key in keys
        )
        for r in five[1:]
    ):
        raise ValueError("Three cold production five-leg exports differ")
    browser_reports += [
        browser("normal", "included"),
        browser("over-budget", "omitted"),
    ]

    def lifecycle(mode):
        baseline = audit("before-lifecycle-" + mode)
        script = "/tmp/briefing-production-lifecycle.mjs"
        copy_to_backend(tools / "production-lifecycle.mjs", script)
        output = "/tmp/briefing-production-lifecycle-" + mode
        result = json.loads(
            owner.compose(
                "exec",
                "-T",
                "--user",
                "appuser",
                "starlink-location",
                "node",
                script,
                "http://mission-planner",
                mode,
                fixtures["five-leg"]["id"],
                fixtures["normal"]["id"],
                output,
                timeout=110,
            ).splitlines()[-1]
        )
        destination = owner.root / "lifecycle" / mode
        destination.mkdir(parents=True)
        owner.compose(
            "cp", f"starlink-location:{output}/.", str(destination), timeout=30
        )
        if mode == "concurrent":
            inspect_download(
                (destination / "first.zip").read_bytes(),
                result["first"]["value"]["headers"],
                "included",
            )
            inspect_download(
                (destination / "second.zip").read_bytes(),
                result["second"]["headers"],
                "omitted",
            )
        audit("after-lifecycle-" + mode, baseline)
        return result

    # Disconnects count against the existing rate limiter too.
    time.sleep(60)
    lifecycle_reports = [
        lifecycle(mode) for mode in ("concurrent", "map", "pdf", "verify")
    ]

    def restart_fault(render="", application=""):
        owner.env.update(BRIEFING_RENDER_FAULT=render, BRIEFING_APP_FAULT=application)
        owner.compose(
            "up",
            "-d",
            "--force-recreate",
            "--no-deps",
            "--wait",
            "--wait-timeout",
            "150",
            "starlink-location",
            timeout=180,
        )
        owner.compose(
            "up", "-d", "--force-recreate", "--no-deps", "mission-planner", timeout=60
        )

    # The observer belongs to this backend instance; preserve it before restart.
    # Application/proxy logs and each request's private owner remain audit evidence.
    owner.finish_observer()
    fault_reports = []
    for fault in ("pdf", "evidence", "publication"):
        restart_fault(application=fault)
        fault_reports.append(download("normal", "omitted", "fault-" + fault, fault))
    restart_fault(render="print-hang")
    fault_reports.append(
        download("normal", "omitted", "fault-print-deadline", "deadline")
    )
    restart_fault()

    imported = []
    for label in ("normal-disabled", "normal"):
        content = (owner.root / "downloads" / label / "download.zip").read_bytes()
        response, _, _ = api.request(
            "POST", "/api/v2/missions/import", multipart=(label + ".zip", content)
        )
        result = json.loads(response)
        if result.get("success") is not True:
            raise ValueError("Real ZIP import failed: " + response.decode())
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            expected = json.loads(archive.read("mission.json"))
            actual, _, _ = api.request("GET", "/api/v2/missions/" + expected["id"])
            actual = json.loads(actual)
            if actual["id"] != expected["id"] or [
                leg["route_id"] for leg in actual["legs"]
            ] != [leg["route_id"] for leg in expected["legs"]]:
                raise ValueError("ZIP import changed original route ownership")
            source_proof = json.loads(
                backend_python(
                    "import json,sys; from pathlib import Path; from hashlib import sha256; "
                    "print(json.dumps({name:sha256(Path('/data/routes',Path(name).name).read_bytes()).hexdigest() for name in json.loads(sys.argv[1])}))",
                    json.dumps(
                        [
                            name
                            for name in archive.namelist()
                            if name.startswith("routes/") and name.endswith(".kml")
                        ]
                    ),
                ).splitlines()[-1]
            )
            if any(
                sha256(archive.read(name)).hexdigest() != digest
                for name, digest in source_proof.items()
            ):
                raise ValueError("ZIP import changed original KML bytes")
        imported.append(
            {
                "package": label,
                "response": result,
                "actualMission": actual,
                "originalRouteHashes": source_proof,
            }
        )
    (owner.root / "roundtrip-imports.json").write_text(json.dumps(imported, indent=2))

    (owner.root / "production-downloads.json").write_text(json.dumps(reports, indent=2))
    return {
        "fixtureKind": "synthetic providers and supported API mission/KML inputs",
        "downloads": reports,
        "browser": browser_reports,
        "lifecycle": lifecycle_reports,
        "faults": fault_reports,
        "runtimeAudits": audit_reports,
        "legacyComparison": legacy_comparison,
        "roundtripImports": imported,
        "customerAcceptance": "pending",
    }
