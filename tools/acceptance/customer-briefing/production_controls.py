"""Real source capture and ZIP downloads through production Nginx."""

import csv
import io
import json
import time
import zipfile
from hashlib import sha256
from math import radians, sin, cos, asin, sqrt
from datetime import datetime, timedelta, timezone
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


def assert_scenario(case, report):
    """Required behavior comes from fixture inputs, not renderer self-consistency."""
    if case == "over-budget":
        if report.get("warning") != "page-budget":
            raise ValueError("Over-budget input must reach page-budget omission")
        return
    if case == "cached-missing-route":
        if report.get("warning") != "data":
            raise ValueError("Missing route must retain legacy with data omission")
        return
    count = {"two-page": 2, "three-page": 3, "five-leg": 5}.get(case)
    if count is not None and report.get("pageCount") != count:
        raise ValueError(
            f"Wrong actual page count for {case}: {report.get('pageCount')}"
        )
    evidence = report["evidence"]
    legs = evidence["legs"]
    if len(legs) != (5 if case == "five-leg" else 1):
        raise ValueError("Wrong number of captured legs")
    maps = evidence["render"]["maps"]
    if case == "missing-map":
        if not any(
            value["status"] == "unavailable" and value["warnings"]
            for value in maps.values()
        ):
            raise ValueError("Missing-map input did not exercise a reasoned fallback")
    elif any(value["status"] != "primary" for value in maps.values()):
        raise ValueError(
            "Representative supported route did not retain useful maps: " + case
        )
    if case == "five-leg" and (
        [page["legId"] for page in evidence["pages"]] != [leg["legId"] for leg in legs]
        or any(page["kind"] != "primary" for page in evidence["pages"])
    ):
        raise ValueError("Five-leg page ownership/order differs from submitted inputs")
    base = datetime(2026, 10, 25, 14, tzinfo=timezone.utc)
    if case == "midnight":
        base += timedelta(hours=60)
    if case == "dst":
        base = datetime(2026, 11, 1, 5, tzinfo=timezone.utc)
    if case == "adjusted":
        base += timedelta(hours=2)
    duration = timedelta(minutes=10 if case == "short" else 240)

    def instant(value):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    for number, leg in enumerate(legs):
        canonical = leg["canonical"]
        bounds = list(map(instant, canonical["utcBounds"]))
        expected_start = base + timedelta(days=number)
        if bounds[0] != expected_start or (
            case != "spliced" and bounds[1] != expected_start + duration
        ):
            raise ValueError(
                "Exact flight bounds changed from submitted UTC inputs: " + case
            )
        if case == "spliced":

            def distance(a, b):
                lat1, lon1, lat2, lon2 = map(radians, (*a, *b))
                return (
                    2
                    * 3440.065
                    * asin(
                        sqrt(
                            sin((lat2 - lat1) / 2) ** 2
                            + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
                        )
                    )
                )

            diversion_hours = (
                distance((35, -103.5), (37, -102)) + distance((37, -102), (35, -100.5))
            ) / 450
            expected_end = expected_start + timedelta(hours=2 + diversion_hours)
            if abs((bounds[1] - expected_end).total_seconds()) > 0.00001:
                raise ValueError(
                    "Configured manual splice timing was ignored or changed"
                )
        intervals = canonical["intervals"]
        if (
            not intervals
            or instant(intervals[0]["startUtc"]) != bounds[0]
            or instant(intervals[-1]["endUtc"]) != bounds[1]
        ):
            raise ValueError("Canonical interval coverage lost flight endpoints")
        if any(a["endUtc"] != b["startUtc"] for a, b in zip(intervals, intervals[1:])):
            raise ValueError("Canonical intervals have gaps or overlap")
        if case == "incomplete-x" and any(
            item["decisions"][2]["value"] != "?" for item in intervals
        ):
            raise ValueError("Unspecified X-Band was promoted to certainty")
        if case in {"subminute", "nested-outage"}:
            down = [
                item
                for item in intervals
                if all(d["value"] == "Down" for d in item["decisions"])
            ]
            a = base + timedelta(minutes=60, seconds=3)
            b = base + timedelta(
                minutes=60, seconds=7 if case == "nested-outage" else 5
            )
            if (
                not down
                or instant(down[0]["startUtc"]) != a
                or instant(down[-1]["endUtc"]) != b
            ):
                raise ValueError(
                    "Brief total outage changed exact configured intersection"
                )
            if not any(
                row["clock"]["start"].count(":") == 2
                and row["clock"]["end"].count(":") == 2
                for row in leg["customerRows"]
                if "All transports unavailable" in row["impact"]
            ):
                raise ValueError("Brief total outage lost second-precision clocks")
        if case in {"short", "ar-sof"}:
            if case == "short" and not all(
                any(r["kind"] == "sof" for r in item["restrictions"])
                for item in intervals
            ):
                raise ValueError("Short-flight SOF did not cover the entire flight")
            if case == "ar-sof" and (
                not all(
                    any(r["kind"] == "ar" for r in item["restrictions"])
                    for item in intervals
                )
                or not any(
                    {r["kind"] for r in item["restrictions"]} >= {"sof", "ar"}
                    for item in intervals
                )
            ):
                raise ValueError("Full-flight AR/SOF overlap was lost")
        if case == "dst" and not any(
            "EDT" in row["clock"]["start"] or "EST" in row["clock"]["end"]
            for row in leg["customerRows"]
        ):
            raise ValueError("DST fold lost explicit offset identity")
        if case == "midnight" and not any(
            "Oct" in row["clock"]["start"] or "Oct" in row["clock"]["end"]
            for row in leg["customerRows"]
        ):
            raise ValueError("Midnight rows lost date disambiguation")


def assert_observations(result, baseline, *, renders, cancelled=False):
    new = set(result["observations"]) - set(baseline["observations"])
    if len(new) != renders:
        raise ValueError(
            f"Missing/extra per-request renderer observations for {renders} renderer request(s): expected {renders}, observed {len(new)}"
        )
    for request in new:
        observation = result["observations"][request]
        if not all(
            observation[key]
            for key in (
                "nodeIdentityRecorded",
                "pythonIdentityRecorded",
                "browserIdentityRecorded",
                "listenerRecorded",
                "stages",
            )
        ):
            raise ValueError("Incomplete owned renderer evidence: " + request)
        if not cancelled and not observation["finalCleanupRecorded"]:
            raise ValueError("Final request cleanup evidence missing: " + request)


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
        if included != (status == "included") or any(
            listed.count(name) != (1 if included else 0)
            or structure["mission_exports"].count(name) != (1 if included else 0)
            for name in (PDF, EVIDENCE)
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
    for category in ("landmark", "satellite"):
        api.request(
            "POST",
            "/api/pois/",
            data={
                "name": "Synthetic acceptance " + category,
                "latitude": 35 if category == "landmark" else 0,
                "longitude": -102,
                "category": category,
                "description": "Identifiable synthetic roundtrip acceptance POI",
                "mission_id": (
                    fixtures["normal"]["id"] if category == "landmark" else None
                ),
                "route_id": (
                    fixtures["normal"]["legs"][0]["route_id"]
                    if category == "landmark"
                    else None
                ),
            },
        )
    reports = []
    tools = (
        Path(owner.env["BRIEFING_SOURCE_ROOT"]) / "tools/acceptance/customer-briefing"
    )

    def copy_to_backend(source, destination):
        if not destination.startswith("/tmp/briefing-"):
            raise ValueError("Acceptance copies must use task-private temporary paths")
        owner.compose("cp", str(source), f"starlink-location:{destination}", timeout=30)
        owner.compose(
            "exec",
            "-T",
            "--user",
            "root",
            "starlink-location",
            "chown",
            "appuser:appuser",
            destination,
            timeout=30,
        )

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

    def audit(label, baseline=None, legacy_disabled=False, renders=0, cancelled=False):
        result = json.loads(backend_python(audit_code).splitlines()[-1])
        if owner.ownership.get("observer") and not result["observerAlive"]:
            raise ValueError("Owned runtime observer is not alive: " + label)
        if baseline is not None:
            changed = sorted(
                name
                for name in result["sourceHashes"].keys()
                | baseline["sourceHashes"].keys()
                if result["sourceHashes"].get(name)
                != baseline["sourceHashes"].get(name)
            )
            result["changedSources"] = changed
            # The unmodified disabled legacy path republishes generated POIs.
            # Record that behavior; snapshot-fed enabled exports must change nothing.
            if changed and (not legacy_disabled or changed != ["/data/pois.json"]):
                raise ValueError(
                    "Export changed persisted inputs: " + label + ": " + str(changed)
                )
            assert_observations(result, baseline, renders=renders, cancelled=cancelled)
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
        audit(
            "after-browser-" + case + "-" + status,
            baseline,
            status == "disabled",
            renders=0 if status == "disabled" else 1,
        )
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
        if case == "spliced":
            from production_seed import kml, BASE

            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                original = archive.read("routes/briefing-spliced-route-1.kml")
                if original != kml(BASE, timedelta(hours=4)):
                    raise ValueError("Spliced export changed original import KML bytes")
            report["originalPlannedKmlSha256"] = sha256(original).hexdigest()
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
        audit(
            "after-download-" + label,
            baseline,
            status == "disabled",
            renders=(
                0
                if status == "disabled"
                or report["warning"] in {"data", "snapshot", "busy"}
                else 1
            ),
        )
        if status != "disabled" and not label.startswith("fault-"):
            assert_scenario(case, report)
        return report

    original_pois = backend_python(
        "import base64; from pathlib import Path; print(base64.b64encode(Path('/data/pois.json').read_bytes()).decode())"
    ).splitlines()[-1]
    download("normal", "disabled", "normal-disabled")
    browser_reports = [browser("normal", "disabled")]
    backend_python(
        "import base64,sys; from pathlib import Path; Path('/data/pois.json').write_bytes(base64.b64decode(sys.argv[1]))",
        original_pois,
    )
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
    observer_count = 0

    def start_observer():
        nonlocal observer_count
        observer_count += 1
        observer = "/tmp/briefing-production-observer.py"
        copy_to_backend(tools / "production_observer.py", observer)
        owner.ownership["observer"] = {
            "service": "starlink-location",
            "script": observer,
            "output": "/tmp/briefing-production-observations",
            "evidenceName": "runtime-observations-" + str(observer_count),
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

        readiness = json.loads(backend_python(audit_code).splitlines()[-1])
        if not readiness["observerAlive"]:
            raise ValueError("Owned observer did not become ready")

    start_observer()
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
        audit(
            "after-lifecycle-" + mode,
            baseline,
            renders=1,
            cancelled=mode != "concurrent",
        )
        return result

    # Disconnects count against the existing rate limiter too.
    time.sleep(60)
    lifecycle_reports = [
        lifecycle(mode) for mode in ("concurrent", "map", "pdf", "verify")
    ]

    def restart_fault(render="", application=""):
        owner.finish_observer()
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
        start_observer()

    # The observer belongs to this backend instance; preserve it before restart.
    # Application/proxy logs and each request's private owner remain audit evidence.
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
        owner.finish_observer()
        owner.compose("stop", "starlink-location", timeout=40)
        owner.compose(
            "run",
            "--rm",
            "--no-deps",
            "starlink-location",
            "python",
            "-c",
            "import shutil; from pathlib import Path; "
            "[shutil.rmtree(p,ignore_errors=True) for p in ('data/missions','/data/routes')]; "
            "Path('/data/pois.json').unlink(missing_ok=True)",
            timeout=30,
        )
        restart_fault()
        content = (owner.root / "downloads" / label / "download.zip").read_bytes()
        response, _, _ = api.request(
            "POST", "/api/v2/missions/import", multipart=(label + ".zip", content)
        )
        result = json.loads(response)
        if result.get("success") is not True or result.get("warnings"):
            raise ValueError("Real ZIP import failed: " + response.decode())
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            expected = json.loads(archive.read("mission.json"))
            actual, _, _ = api.request("GET", "/api/v2/missions/" + expected["id"])
            actual = json.loads(actual)
            if actual != expected:
                raise ValueError("ZIP import changed original mission/leg content")
            expected_pois = [
                poi
                for name in archive.namelist()
                if name.startswith("pois/") and name.endswith(".json")
                for poi in json.loads(archive.read(name))["pois"]
                if poi["description"]
                == "Identifiable synthetic roundtrip acceptance POI"
            ]
            poi_response, _, _ = api.request("GET", "/api/pois/?active_only=false")
            actual_pois = json.loads(poi_response)["pois"]

            # Legacy POI create/import assigns fresh creation/update clocks.
            # Ownership, location, type and every other stored content field must match.
            def poi_content(poi):
                return {
                    key: value
                    for key, value in poi.items()
                    if key not in {"created_at", "updated_at", "active"}
                }

            actual_by_id = {poi["id"]: poi for poi in actual_pois}
            if (
                len(expected_pois) != 2
                or result["satellites_imported"] < 1
                or result["pois_imported"] < 1
            ):
                raise ValueError(
                    "Nonempty identifiable POI import control was not exercised"
                )
            for poi in expected_pois:
                imported_poi = actual_by_id.get(poi["id"], {})
                if any(
                    imported_poi.get(key) != value
                    for key, value in poi_content(poi).items()
                ):
                    raise ValueError(
                        "ZIP import changed identifiable user/satellite POI content"
                    )
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
                "identifiablePois": expected_pois,
                "poiImportClockExclusions": ["created_at", "updated_at"],
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
