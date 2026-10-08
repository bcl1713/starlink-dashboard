"""Real source capture and ZIP downloads through production Nginx."""

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

    def browser(case, status):
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

    def download(case, status, attempt=None):
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
        report.update(case=case, attempt=label, proxyTotalSeconds=elapsed)
        if status == "included":
            report["actualPdfInspection"] = pdf_inspection(destination, label)
        (destination / "inspection.json").write_text(json.dumps(report, indent=2))
        reports.append(report)
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
    for case in fixtures:
        download(case, "omitted" if case == "over-budget" else "included")
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
    (owner.root / "production-downloads.json").write_text(json.dumps(reports, indent=2))
    return {
        "fixtureKind": "synthetic providers and supported API mission/KML inputs",
        "downloads": reports,
        "browser": browser_reports,
        "customerAcceptance": "pending",
    }
