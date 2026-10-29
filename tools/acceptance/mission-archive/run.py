#!/usr/bin/env python3
"""Exact production images, dense synthetic observations, HTTP and browser proof."""

import argparse
import concurrent.futures
import csv
import hashlib
import importlib.util
import io
import json
import os
import shutil
import sqlite3
import sys
import time
import zipfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from responsiveness import dashboard

ROOT = Path(__file__).resolve().parents[3]
OPERATOR = ROOT / "tools/acceptance/operator-journal"
sys.path.insert(0, str(OPERATOR))
spec = importlib.util.spec_from_file_location(
    "operator_archive_runner", OPERATOR / "run.py"
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
MISSION = "synthetic-mission-a"
CONTROL = "/api/_synthetic/large-export"


def request(origin, path, body=None):
    call = Request(
        origin + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
    )
    return urlopen(call, timeout=620)


def data(origin, path=CONTROL, body=None):
    with request(origin, path, body) as response:
        return json.load(response)


def download(origin, endpoint, representation, target):
    path = f"/api/v2/missions/{MISSION}/{endpoint}?telemetry_format={representation}"
    with request(origin, path, {}) as response:
        if response.status == 200:
            with target.open("wb") as output:
                shutil.copyfileobj(response, output, 65536)
            return
        job = json.load(response)
    deadline = time.monotonic() + 620
    while job["state"] in ("queued", "preparing"):
        if time.monotonic() >= deadline:
            raise TimeoutError("Export did not reach ready state")
        time.sleep(0.1)
        job = data(
            origin, f"/api/v2/missions/{MISSION}/export-preparations/{job['id']}"
        )
    if job["state"] != "ready":
        raise RuntimeError(f"Export failed: {job}")
    with request(origin, job["download_url"]) as response, target.open("wb") as output:
        shutil.copyfileobj(response, output, 65536)


def verify(path, expected, representation, index_path):
    digest, count, metrics = hashlib.sha256(), 0, set()
    with sqlite3.connect(index_path) as index, zipfile.ZipFile(path) as package:
        manifest = json.loads(package.read("manifest.json"))
        for name, checksum in manifest["archive_components"]["checksums"].items():
            member_digest = hashlib.sha256()
            with package.open(name) as member:
                while block := member.read(65536):
                    member_digest.update(block)
            assert member_digest.hexdigest() == checksum, name
        prefix = "telemetry/legs/001/"
        if representation == "compact":
            index.execute(
                "CREATE TABLE series (id TEXT PRIMARY KEY,metric TEXT,labels TEXT)"
            )
            with package.open(prefix + "series.csv") as source:
                rows = csv.DictReader(io.TextIOWrapper(source, encoding="utf-8"))
                index.executemany(
                    "INSERT INTO series VALUES (?,?,?)",
                    (
                        (row["series_id"], row["metric"], row["labels_json"])
                        for row in rows
                    ),
                )
        with package.open(prefix + "observations.csv") as source:
            for row in csv.DictReader(io.TextIOWrapper(source, encoding="utf-8")):
                if representation == "compact":
                    metric, labels = index.execute(
                        "SELECT metric,labels FROM series WHERE id=?",
                        (row["series_id"],),
                    ).fetchone()
                else:
                    metric, labels = row["metric"], row["labels_json"]
                item = {
                    "timestamp": row["timestamp_utc"],
                    "metric": metric,
                    "labels": json.loads(labels),
                    "value": float(row["value"]) if row["value"] else None,
                    "observed_at": row["source_observed_at_utc"] or None,
                }
                availability = (
                    "missing"
                    if item["value"] is None
                    else (
                        "source_freshness_unknown"
                        if item["labels"].get("source") == "cached_last_known_proxy"
                        else "observed"
                    )
                )
                assert row["availability"] == availability
                digest.update((json.dumps(item, sort_keys=True) + "\n").encode())
                metrics.add(metric)
                count += 1
        assert count == expected["rows"] == 300000
        assert digest.hexdigest() == expected["digest"]
        assert {
            "starlink_dish_latitude_degrees",
            "starlink_dish_longitude_degrees",
            "starlink_dish_speed_knots",
            "starlink_dish_altitude_feet",
            "starlink_dish_heading_degrees",
        } <= metrics
        assert "operations/audit.jsonl" in package.namelist()
        assert "operations/journal.json" in package.namelist()
        audit = package.read("operations/audit.jsonl")
        result = {
            "observations": count,
            "source_digest": digest.hexdigest(),
            "metric_count": len(metrics),
            "journal_revisions": len(audit.splitlines()),
            "bytes": path.stat().st_size,
            "telemetry_table_bytes": package.getinfo(
                prefix + "observations.csv"
            ).file_size
            + (
                package.getinfo(prefix + "series.csv").file_size
                if representation == "compact"
                else 0
            ),
        }
    index_path.unlink()
    return result


def case(owner, origin, label, endpoint, representation):
    expected = data(origin)
    assert expected["old_input_accounting"] > 128 * 1024 * 1024
    path = owner.root / (label + ".zip")
    before, peak = expected["rss_bytes"], expected["rss_bytes"]
    started = time.monotonic()
    baseline = dashboard(origin)
    assert baseline["available"], "Synthetic metric source did not initialize"
    latencies, unavailable = [], 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(download, origin, endpoint, representation, path)
        while not future.done():
            status = dashboard(origin)
            latencies.append(status["seconds"])
            unavailable += int(
                not baseline["available"] <= status["available"]
                or not baseline["status_available"] <= status["status_available"]
            )
            peak = max(peak, data(origin)["rss_bytes"])
            time.sleep(0.1)
        future.result()
    generated_seconds = time.monotonic() - started
    assert unavailable == 0, f"Export interrupted metrics {unavailable} times"
    assert max(latencies, default=0) < 2, "Dashboard status became unresponsive"
    proof = verify(
        path, expected, representation, owner.root / (label + "-verify.sqlite3")
    )
    proof.update(
        seconds=time.monotonic() - started,
        generation_seconds=generated_seconds,
        dashboard_polls=len(latencies),
        dashboard_max_seconds=max(latencies, default=0),
        dashboard_unavailable=unavailable,
        rss_baseline_bytes=before,
        rss_peak_bytes=peak,
        old_input_accounting=expected["old_input_accounting"],
        representation=representation,
        endpoint=endpoint,
        source_state=expected["state"],
        high_cardinality=expected["high_cardinality"],
    )
    (owner.root / (label + ".json")).write_text(json.dumps(proof, indent=2))
    return proof


def qualify(owner):
    origin = owner.ownership["originTraversal"]["origin"]
    proof = {}
    proof["active_full"] = case(owner, origin, "active-full", "export", "full")
    proof["active_compact"] = case(
        owner, origin, "active-compact", "export-preparations", "compact"
    )
    # The old list reader still demonstrates the original rejection on these rows.
    container = owner.compose("ps", "-q", "starlink-location", timeout=15).strip()
    source = data(origin)
    script = "\n".join(
        [
            "from datetime import datetime",
            "from pathlib import Path",
            "from app.services.telemetry_archive.store import ArchiveStore",
            f"archive=ArchiveStore(Path({source['archive_path']!r}))",
            "try:",
            " archive.samples(datetime.fromisoformat('2026-01-01T00:00:00+00:00'), datetime.fromisoformat('2026-01-02T00:00:00+00:00'), budget=[128*1024*1024])",
            "except RuntimeError as error:",
            " assert str(error)=='Telemetry archive input size limit exceeded'",
            " print('Original input limit reproduced')",
            "else:",
            " raise AssertionError('Old path unexpectedly accepted the dense input')",
        ]
    )
    proof["original_limit"] = owner.execute(
        [
            "docker",
            "exec",
            "--user",
            "1000:1000",
            "--env",
            "PYTHONUSERBASE=/home/appuser/.local",
            container,
            "python",
            "-c",
            script,
        ],
        timeout=120,
    ).strip()
    # Hold a real snapshot, measure an independent recording commit, then expire capture.
    data(origin, body={"action": "pause"})
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(
            data, origin, f"/api/v2/missions/{MISSION}/export-preparations", {}
        )
        deadline = time.monotonic() + 15
        while not data(origin)["entered"]:
            if time.monotonic() >= deadline:
                raise TimeoutError("Paused source was never entered")
            time.sleep(0.05)
        proof["paused_reader_writer"] = data(origin, body={"action": "write"})
        assert proof["paused_reader_writer"]["writer_seconds"] < 2
        data(origin, body={"action": "deadline"})
        try:
            pending.result(timeout=15)
        except HTTPError as error:
            assert error.code == 504
            assert json.load(error)["detail"]["code"] == "mission_archive_deadline"
            proof["pre_ack_deadline"] = True
        else:
            raise AssertionError("Expired capture was acknowledged")
    data(origin, body={"action": "release"})
    assert data(origin)["capture_owners"] == 0
    # A save during the expensive telemetry capture must retain the original plan.
    original = data(origin, f"/api/v2/missions/{MISSION}")["name"]
    data(origin, body={"action": "pause"})
    target = owner.root / "mid-mission-snapshot.zip"
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(download, origin, "export", "compact", target)
        deadline = time.monotonic() + 15
        while not data(origin)["entered"]:
            if time.monotonic() >= deadline:
                raise TimeoutError("Live snapshot capture was never entered")
            time.sleep(0.05)
        data(origin, body={"action": "rename", "name": "Updated while exporting"})
        data(origin, body={"action": "write"})
        data(origin, body={"action": "release"})
        pending.result(timeout=60)
    with zipfile.ZipFile(target) as archive:
        assert json.loads(archive.read("mission.json"))["name"] == original
    proof["mid_mission_snapshot"] = verify(
        target, data(origin), "compact", owner.root / "mid-mission-verify.sqlite3"
    )
    data(origin, body={"action": "rename", "name": original})
    data(origin, body={"action": "capacity", "bytes": 128})
    try:
        data(origin, f"/api/v2/missions/{MISSION}/export", {})
    except HTTPError as error:
        assert error.code == 413
        assert json.load(error)["detail"]["code"] == "mission_archive_capacity"
        proof["capacity"] = True
    else:
        raise AssertionError("Capacity rejection was not explicit")
    data(origin, body={"action": "capacity"})
    data(origin, body={"action": "seal"})
    proof["sealed_full"] = case(
        owner, origin, "sealed-full", "export-preparations", "full"
    )
    proof["sealed_compact"] = case(owner, origin, "sealed-compact", "export", "compact")
    data(origin, body={"action": "recover"})
    proof["recovering_full"] = case(owner, origin, "recovering-full", "export", "full")
    proof["recovering_compact"] = case(
        owner, origin, "recovering-compact", "export-preparations", "compact"
    )
    data(origin, body={"action": "seed", "high_cardinality": True})
    proof["cardinality_compact"] = case(
        owner, origin, "cardinality-compact", "export-preparations", "compact"
    )
    browser = ROOT / "tools/acceptance/mission-archive/browser.mjs"
    playwright = os.environ.get(
        "STARLINK_ACCEPTANCE_PLAYWRIGHT_MODULE",
        str(ROOT / "frontend/mission-planner/node_modules/playwright/index.mjs"),
    )
    owner.execute(
        ["node", str(browser), origin, str(owner.root), playwright], timeout=120
    )
    proof["browser"] = json.loads((owner.root / "browser.json").read_text())
    (owner.root / "large-export.json").write_text(json.dumps(proof, indent=2))
    return proof


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--evidence", required=True)
    args = parser.parse_args()
    os.environ["OPERATOR_ACCEPTANCE_ENTRYPOINT"] = "large_export_fixture"
    os.environ["OPERATOR_ACCEPTANCE_HEALTH_PATH"] = "/health"
    runner.run(
        args.candidate,
        args.project,
        args.evidence,
        qualification=qualify,
    )
