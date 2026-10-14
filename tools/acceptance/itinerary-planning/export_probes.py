"""Real HTTP measurements retain every failure, header time, and partial body."""

import argparse
import http.client
import json
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit


def probe_request(url, *, method="GET", payload=None, seconds=2, retain_body=True):
    parsed = urlsplit(url)
    connection_type = (
        http.client.HTTPSConnection
        if parsed.scheme == "https"
        else http.client.HTTPConnection
    )
    connection = connection_type(parsed.hostname, parsed.port, timeout=seconds)
    started = time.monotonic()
    result = {
        "path": parsed.path,
        "method": method,
        "status": None,
        "headers_seconds": None,
        "body_seconds": None,
        "elapsed_seconds": None,
        "bytes": 0,
        "sha256": None,
        "error": None,
    }
    digest, blocks = sha256(), []
    expired = threading.Event()
    transport = {}

    def expire():
        expired.set()
        sock = transport.get("socket")
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    watchdog = threading.Timer(seconds, expire)
    watchdog.start()
    try:
        connection.connect()
        transport["socket"] = connection.sock
        connection.sock.settimeout(max(0.001, seconds - (time.monotonic() - started)))
        body = json.dumps(payload).encode() if payload is not None else None
        connection.request(
            method,
            parsed.path + ("?" + parsed.query if parsed.query else ""),
            body=body,
            headers={"Content-Type": "application/json"} if body else {},
        )
        response = connection.getresponse()
        result.update(
            status=response.status, headers_seconds=time.monotonic() - started
        )
        length = response.getheader("Content-Length")
        while not response.isclosed():
            remaining = seconds - (time.monotonic() - started)
            if remaining <= 0:
                raise TimeoutError()
            # HTTPResponse can own the socket after the connection marks itself closed.
            sock = connection.sock or response.fp.raw._sock
            sock.settimeout(remaining)
            try:
                block = response.read(65536)
            except http.client.IncompleteRead as exc:
                block = exc.partial
                result["error"] = "incomplete-body"
            if block:
                result["bytes"] += len(block)
                digest.update(block)
                if retain_body:
                    blocks.append(block)
            if not block or result["error"]:
                break
        if length is not None and result["bytes"] != int(length):
            result["error"] = "incomplete-body"
    except TimeoutError:
        result["error"] = "deadline"
    except (OSError, ValueError, http.client.HTTPException) as exc:
        result["error"] = "deadline" if expired.is_set() else type(exc).__name__
    finally:
        watchdog.cancel()
        connection.close()
        watchdog.join()
        if expired.is_set():
            result["error"] = "deadline"
        result["body_seconds"] = time.monotonic() - started
        result["elapsed_seconds"] = result["body_seconds"]
        result["sha256"] = digest.hexdigest()
        if retain_body:
            result["body"] = b"".join(blocks)
    return result


def probe_series(origin, mission_id, *, seconds, output):
    paths = ["/health", "/api/status", f"/api/v2/missions/{mission_id}"]
    requests = []
    until = time.monotonic() + seconds
    with ThreadPoolExecutor(max_workers=3) as workers:
        while time.monotonic() < until or not requests:
            futures = [
                workers.submit(probe_request, origin + path, retain_body=False)
                for path in paths
            ]
            requests.extend(future.result() for future in futures)
            if time.monotonic() < until:
                time.sleep(min(0.1, until - time.monotonic()))
    failures = [
        r
        for r in requests
        if r["error"] or r["status"] != 200 or r["elapsed_seconds"] > 2
    ]
    report = {
        "request_deadline_seconds": 2,
        "requests": requests,
        "failures": failures,
        "maximum_seconds": max(r["elapsed_seconds"] for r in requests),
    }
    Path(output).write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", required=True)
    parser.add_argument("--mission-id", required=True)
    parser.add_argument("--seconds", type=float, default=10)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = probe_series(
        args.origin, args.mission_id, seconds=args.seconds, output=args.output
    )
    print(
        json.dumps({key: value for key, value in report.items() if key != "requests"})
    )
    raise SystemExit(bool(report["failures"]))
