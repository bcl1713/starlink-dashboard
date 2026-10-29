#!/usr/bin/env python3
"""Bounded, independent read-only Prometheus evidence for issue 393.

This observer never creates or writes the native run directory. Its evidence is
descriptive; qualification remains the responsibility of the native run/review.
"""

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import re
import signal
import socket
import threading
import time
import urllib.parse


STATE = Path("/home/oracle-worker/Work/starlink-dashboard/.superpowers/sdd/2026-10-28-issue393-clean-soak")
MAX_BODY = 1024 * 1024
MAX_TAIL = 256 * 1024
WARMUP = 120
QUERIES = {
    "mission_active_info": "mission_active_info",
    "mission_gauge_count": 'count({__name__=~"mission_.*"})',
    "poi_eta_count": "count(starlink_eta_poi_seconds)",
    "scrape_up": 'up{job="starlink-location"}',
    "scrape_duration": 'scrape_duration_seconds{job="starlink-location"}',
    "scrape_samples": 'scrape_samples_scraped{job="starlink-location"}',
}


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def native_file(run, name):
    path = run / name
    if path.is_symlink():
        raise ValueError(f"Native evidence must not be a symlink: {path}")
    return path


def proof(path):
    if not path.exists():
        return None
    data = path.read_bytes()
    item = {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    try:
        payload = json.loads(data)
        item["native_status"] = payload.get("status")
        if "qualification_clean" in payload:
            item["native_qualification_clean"] = payload["qualification_clean"]
    except (ValueError, AttributeError) as error:
        item["parse_error"] = str(error)
    return item


def latest_sample(run):
    path = native_file(run, "samples.jsonl")
    if not path.exists():
        return {"phase": "setup", "sample_available": False}
    with path.open("rb") as stream:
        stream.seek(0, 2)
        size = stream.tell()
        offset = max(0, size - MAX_TAIL)
        stream.seek(offset)
        tail = stream.read(MAX_TAIL)
    lines = tail.splitlines(keepends=True)
    if offset and lines:
        lines = lines[1:]
    incomplete = bool(lines and not lines[-1].endswith(b"\n"))
    if incomplete:
        lines.pop()
    if not lines:
        return {"phase": "setup", "sample_available": False, "partial_tail": incomplete}
    row = json.loads(lines[-1])
    seconds = row.get("seconds")
    if not isinstance(seconds, (int, float)) or not math.isfinite(seconds):
        raise ValueError("Native sample seconds is not finite")
    phase = row.get("phase")
    if phase not in ("warmup", "measured"):
        raise ValueError("Native sample phase is not warmup or measured")
    return {
        "phase": phase,
        "sample_available": True,
        "native_seconds": seconds,
        "warmup_seconds": WARMUP,
        "seconds_from_measured_start": seconds - WARMUP,
        "partial_tail": incomplete,
        "native_sample": row,
    }


def owner_endpoint(run):
    path = native_file(run, "ownership.json")
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    project = data.get("project")
    if not isinstance(project, str) or not re.fullmatch(r"starlink-operator-issue393-clean-[a-z0-9-]+", project):
        raise ValueError("Peer project does not have the required issue393-clean prefix")
    port = data.get("prometheusPort")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Peer Prometheus port must be an integer in 1..65535")
    return project, port


def query(port, expression, deadline):
    started = time.monotonic()
    item = {"expression": expression, "wall_utc": utc(), "monotonic": started}
    connection = None
    watchdog = None
    try:
        remaining = min(5.0, deadline - started)
        if remaining <= 0:
            raise TimeoutError("Observer wall-clock budget exhausted")
        query_deadline = started + remaining
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=remaining)
        connection.connect()
        connected_socket = connection.sock
        def interrupt_http():
            try:
                connected_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        watchdog = threading.Timer(max(0, query_deadline - time.monotonic()), interrupt_http)
        watchdog.start()
        connection.sock.settimeout(max(0.001, query_deadline - time.monotonic()))
        connection.request("GET", "/api/v1/query?" + urllib.parse.urlencode({"query": expression}), headers={"Connection": "close"})
        connection.sock.settimeout(max(0.001, query_deadline - time.monotonic()))
        response = connection.getresponse()
        item["http_status"] = response.status
        item["content_type"] = response.getheader("Content-Type")
        chunks = []
        count = 0
        while True:
            remaining = query_deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Prometheus HTTP request exceeded five-second wall limit")
            if connection.sock is not None:
                connection.sock.settimeout(remaining)
            chunk = response.read1(min(65536, MAX_BODY + 1 - count))
            if not chunk:
                break
            chunks.append(chunk)
            count += len(chunk)
            if count > MAX_BODY:
                item["body_exceeded_limit"] = True
                raise ValueError("Prometheus response exceeds 1 MiB capture limit")
        body = b"".join(chunks)
        item["body_bytes"] = len(body)
        item["body_sha256"] = hashlib.sha256(body).hexdigest()
        text = body.decode("utf-8")
        try:
            payload = json.loads(text)
        except ValueError:
            item["raw_body"] = text
            raise
        item["raw_result"] = payload
        if response.status != 200 or payload.get("status") != "success":
            raise ValueError("Prometheus query did not return HTTP 200/success")
        if not isinstance(payload.get("data", {}).get("result"), list):
            raise ValueError("Prometheus result is not a vector")
    except Exception as error:
        item["probe_error"] = f"{type(error).__name__}: {error}"
    finally:
        if watchdog is not None:
            watchdog.cancel()
            watchdog.join()
        if connection is not None:
            connection.close()
        item["duration_seconds"] = time.monotonic() - started
    return item


def derive(results):
    def number(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("Nonfinite Prometheus value")
        return parsed

    def vector(name):
        row = results[name]
        if "probe_error" in row:
            return None
        return row["raw_result"]["data"]["result"]

    active = vector("mission_active_info")
    up = vector("scrape_up")
    derived = {
        "current_identity_count": None if active is None else len(active),
        "mission_identity_valid": None if active is None else len(active) <= 1 and all(
            number(item["value"][1]) == 1 and isinstance(item["metric"].get("route_id"), str) and bool(item["metric"]["route_id"])
            for item in active
        ),
        "scrape_healthy": None if up is None else bool(up) and all(number(item["value"][1]) == 1 for item in up),
    }
    for name in ("mission_gauge_count", "poi_eta_count"):
        values = vector(name)
        derived[name] = None if values is None else number(values[0]["value"][1]) if values else 0
    return derived


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-prefix", type=Path, required=True)
    parser.add_argument("--budget-seconds", type=float, required=True)
    args = parser.parse_args()
    state = STATE.resolve(strict=True)
    run = args.run_dir.resolve()
    prefix = args.output_prefix.resolve()
    if run.parent != state or not re.fullmatch(r"(?:preflight|sustained)-[0-9]{3,}", run.name):
        parser.error("run-dir must be a direct STATE/preflight-NNN or STATE/sustained-NNN child")
    if args.run_dir.is_symlink() or prefix.parent != state or prefix.name != "cardinality-" + run.name:
        parser.error("output-prefix must be STATE/cardinality-<run name>; symlink runs are forbidden")
    if not math.isfinite(args.budget_seconds) or not 0 < args.budget_seconds <= 86400:
        parser.error("budget-seconds must be finite and within (0, 86400]")
    start = time.monotonic()
    deadline = start + args.budget_seconds
    stop = threading.Event()
    caught = []
    def on_signal(number, _frame):
        caught.append(number)
        stop.set()
    for number in (signal.SIGINT, signal.SIGTERM):
        signal.signal(number, on_signal)
    stat = Path(f"/proc/{os.getpid()}/stat").read_text().rsplit(") ", 1)[1].split()
    ownership = {
        "purpose": "read-only issue393 independent Prometheus cardinality observer",
        "pid": os.getpid(), "pgid": os.getpgrp(), "start_ticks": int(stat[19]),
        "wall_utc": utc(), "monotonic": start, "deadline_monotonic": deadline,
        "run_dir": str(run), "output_prefix": str(prefix), "warmup_seconds": WARMUP,
        "poll_seconds": 5, "http_timeout_seconds": 5, "body_limit_bytes": MAX_BODY,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "writes_native_run": False,
    }
    with Path(str(prefix) + "-owner.json").open("x") as stream:
        json.dump(ownership, stream, indent=2)
        stream.write("\n")
    counts = {}
    rows = 0
    status = "timeout"
    fatal = None
    markers = {}
    try:
        with Path(str(prefix) + "-samples.jsonl").open("x", buffering=1) as evidence, concurrent.futures.ThreadPoolExecutor(max_workers=len(QUERIES), thread_name_prefix="cardinality-http") as pool:
            while not stop.is_set() and time.monotonic() < deadline:
                tick = time.monotonic()
                markers = {name: native_file(run, name) for name in ("api-capture-summary.json", "run.json")}
                if any(path.exists() for path in markers.values()):
                    status = "finished"
                    break
                row = {"wall_utc": utc(), "monotonic": tick, "observer_seconds": tick - start, "run_dir": str(run)}
                errors = []
                try:
                    row.update(latest_sample(run))
                except Exception as error:
                    row.update(phase="unknown", sample_read_error=f"{type(error).__name__}: {error}")
                    errors.append(row["sample_read_error"])
                try:
                    endpoint = owner_endpoint(run)
                    if endpoint is None:
                        row["setup_state"] = "waiting_for_native_ownership"
                    else:
                        project, port = endpoint
                        row.update(project=project, prometheus_port=port)
                        pending = {name: pool.submit(query, port, expression, deadline) for name, expression in QUERIES.items()}
                        row["queries"] = {name: future.result() for name, future in pending.items()}
                        errors.extend(value["probe_error"] for value in row["queries"].values() if "probe_error" in value)
                        try:
                            row["derived"] = derive(row["queries"])
                        except Exception as error:
                            errors.append(f"Derived result error: {type(error).__name__}: {error}")
                except Exception as error:
                    errors.append(f"{type(error).__name__}: {error}")
                phase = row["phase"]
                bucket = counts.setdefault(phase, {"rows": 0, "probe_errors": 0, "rows_with_probe_errors": 0})
                bucket["rows"] += 1
                bucket["probe_errors"] += len(errors)
                bucket["rows_with_probe_errors"] += bool(errors)
                row.update(probe_errors=errors, measurement_probe_error=phase == "measured" and bool(errors), completed_wall_utc=utc(), completed_monotonic=time.monotonic())
                evidence.write(json.dumps(row, allow_nan=False) + "\n")
                rows += 1
                stop.wait(max(0, min(deadline - time.monotonic(), tick + 5 - time.monotonic())))
            if stop.is_set():
                status = "interrupted"
    except Exception as error:
        status = "interrupted"
        fatal = f"{type(error).__name__}: {error}"
    finally:
        ready = {}
        for name in ("ownership.json", "api-capture-summary.json", "run.json"):
            try:
                ready[name] = proof(native_file(run, name))
            except Exception as error:
                ready[name] = {"proof_error": f"{type(error).__name__}: {error}"}
        summary = {"status": status, "qualification_claim": False, "row_count": rows, "counts_by_phase": counts, "signals": caught, "fatal_error": fatal, "wall_utc": utc(), "monotonic": time.monotonic(), "observer_seconds": time.monotonic() - start, "native_ready_proof": ready, "observer_owner": ownership}
        with Path(str(prefix) + "-summary.json").open("x") as stream:
            json.dump(summary, stream, indent=2, allow_nan=False)
            stream.write("\n")
    return 0 if status == "finished" else 130 if caught else 1


if __name__ == "__main__":
    raise SystemExit(main())
