"""Private application renderer staging and identity-checked process ownership."""

import json
import logging
import os
import shutil
import signal
import subprocess
import tempfile
import time
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path

import psutil

from app.mission.package.customer_artifacts import (
    WARNING_CODES,
    CustomerBriefingArtifacts,
    CustomerBriefingOutcome,
)

from .customer_document import build_customer_mission_document
from .customer_evidence import build_customer_mission_evidence
from .export_cancel import ExportCancelled, check_cancelled
from .snapshot_inputs import canonical_json

STAGING_PARENT = None
NODE = "/usr/local/bin/node"
RENDERER_ENTRY = "/opt/customer-briefing/renderer/briefing-render.mjs"
ASSET_ROOT = "/opt/customer-briefing/assets"
logger = logging.getLogger(__name__)


@contextmanager
def _private_staging():
    root = Path(tempfile.mkdtemp(prefix="customer-briefing-", dir=STAGING_PARENT))
    try:
        yield root
    finally:
        owner_path = root / "python-owner.json"
        safe = not owner_path.exists()
        if owner_path.exists():
            try:
                owner = json.loads(owner_path.read_text())
                safe = owner.get("pid") is None or (
                    owner.get("reaped") is True
                    and owner.get("cleanup", {}).get("survivors") == []
                )
            except (OSError, ValueError, TypeError):
                safe = False
        if safe:
            shutil.rmtree(root)
        else:
            logger.error(
                "Renderer cleanup blocked; retained ownership evidence: %s", owner_path
            )


class RendererFailure(RuntimeError):
    def __init__(self, code):
        super().__init__("Optional customer briefing omitted")
        self.code = code


def _process_record(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1].split()
        return {
            "pid": int(pid),
            "pgid": int(fields[2]),
            "start": fields[19],
            "ppid": int(fields[1]),
            "state": fields[0],
        }
    except (OSError, ValueError, IndexError):
        return None


def _alive(record):
    current = _process_record(record["pid"])
    return current and current["start"] == record["start"] and current["state"] != "Z"


def _collect(child, staging, records):
    def descendants(root):
        if not _alive(root):
            return
        try:
            process = psutil.Process(root["pid"])
            # Recheck identity after opening the process handle, before traversal.
            if not _alive(root):
                return
            for descendant in process.children(recursive=True):
                record = _process_record(descendant.pid)
                if record:
                    records[(record["pid"], record["start"])] = record
        except psutil.Error:
            pass

    # Previously recorded descendants can outlive and be reparented from Node.
    for record in list(records.values()):
        descendants(record)
    try:
        owner = json.loads((Path(staging) / "ownership.json").read_text())
    except (OSError, ValueError):
        return
    # The owner file belongs to this exact root process, including its start ID.
    root = next((r for r in records.values() if r["pid"] == child.pid), None)
    if not root or owner.get("pid") != child.pid or owner.get("start") != root["start"]:
        return
    candidates = [{"pid": owner.get("browserPid"), "start": owner.get("browserStart")}]
    candidates.extend(owner.get("workers", []))
    for candidate in candidates:
        pid, start = candidate.get("pid"), candidate.get("start")
        if not isinstance(pid, int) or not isinstance(start, str):
            continue
        record = _process_record(pid)
        if record and record["start"] == start:
            records[(pid, start)] = record
            descendants(record)


def _signal_record(record, sig):
    if _alive(record):
        try:
            os.kill(record["pid"], sig)
        except ProcessLookupError:
            pass


def _cleanup(child, staging, records, grace):
    _collect(child, staging, records)
    for record in records.values():
        _signal_record(record, signal.SIGTERM)
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline and any(_alive(r) for r in records.values()):
        _collect(child, staging, records)
        time.sleep(min(0.025, max(0, deadline - time.monotonic())))
    # Rescan before forcing only identity-verified owned survivors.
    _collect(child, staging, records)
    for record in records.values():
        _signal_record(record, signal.SIGKILL)
    child.wait(timeout=max(1, grace))
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline and any(_alive(r) for r in records.values()):
        time.sleep(0.01)
    return {"survivors": [r["pid"] for r in records.values() if _alive(r)]}


def run_owned_renderer(
    command, staging, *, cancel, wall_seconds=70, kill_grace_seconds=10
):
    """The emergency guard forces failure; only Node's <=60s report qualifies."""
    check_cancelled(cancel)
    root = Path(staging)
    record_path = root / "python-owner.json"
    owner = {
        "command": command,
        "temporaryPaths": [str(root)],
        "pid": None,
        "pgid": None,
        "reaped": False,
    }
    record_path.write_text(json.dumps(owner))
    child, records, reason = None, {}, None
    try:
        with (root / "renderer.log").open("wb") as log:
            child = subprocess.Popen(
                command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
            )
            record = _process_record(child.pid)
            if record:
                records[(child.pid, record["start"])] = record
            owner.update(
                pid=child.pid, pgid=child.pid, start=record["start"] if record else None
            )
            record_path.write_text(json.dumps(owner))
            deadline = time.monotonic() + wall_seconds
            while child.poll() is None:
                _collect(child, root, records)
                if cancel.is_set():
                    reason = "cancelled"
                    break
                if time.monotonic() >= deadline:
                    reason = "deadline"
                    break
                cancel.wait(min(0.025, max(0, deadline - time.monotonic())))
    except OSError as exc:
        raise RendererFailure("runtime") from exc
    finally:
        if child is not None:
            owner["cleanup"] = _cleanup(child, root, records, kill_grace_seconds)
            owner["reaped"] = child.poll() is not None
            owner["returncode"] = child.returncode
            record_path.write_text(json.dumps(owner))
            if owner["cleanup"]["survivors"] or not owner["reaped"]:
                raise RendererFailure("cleanup")
    if reason == "cancelled":
        raise ExportCancelled("Export cancelled")
    if reason:
        raise RendererFailure(reason)
    return child.returncode


def render_customer_artifacts(snapshot, *, cancel):
    check_cancelled(cancel)
    try:
        payload = build_customer_mission_document(snapshot)
    except (ValueError, KeyError, TypeError, AttributeError):
        return CustomerBriefingOutcome("omitted", "data", None)
    try:
        with _private_staging() as root:
            temp = str(root)
            input_path = root / "payload.json"
            input_path.write_bytes(canonical_json(payload))
            code = run_owned_renderer(
                [NODE, RENDERER_ENTRY, str(input_path), temp, ASSET_ROOT],
                root,
                cancel=cancel,
            )
            check_cancelled(cancel)
            try:
                report = json.loads((root / "render-report.json").read_text())
            except (OSError, ValueError) as exc:
                raise RendererFailure("runtime") from exc
            cleanup = report.get("cleanup") or {}
            if (
                cleanup.get("success") is not True
                or any(
                    cleanup.get(key) is not True
                    for key in (
                        "contextsClosed",
                        "browserExited",
                        "listenerClosed",
                        "childrenReaped",
                    )
                )
                or cleanup.get("survivors") != []
                or cleanup.get("errors") != []
            ):
                raise RendererFailure("cleanup")
            elapsed = report.get("totalMs")
            if not isinstance(elapsed, (int, float)) or not 0 <= elapsed <= 60000:
                raise RendererFailure("deadline")
            if code or report.get("status") != "success":
                safe = report.get("errorCode")
                raise RendererFailure(safe if safe in WARNING_CODES else "runtime")
            if report.get("artifacts") != {"pdfPath": "mission-customer-briefing.pdf"}:
                raise RendererFailure("pdf")
            try:
                pdf = (root / "mission-customer-briefing.pdf").read_bytes()
            except OSError as exc:
                raise RendererFailure("pdf") from exc
            if not pdf.startswith(b"%PDF-") or sha256(pdf).hexdigest() != report.get(
                "artifactHashes", {}
            ).get("pdfPath"):
                raise RendererFailure("pdf")
            try:
                evidence = build_customer_mission_evidence(
                    snapshot, payload, report.get("pagePlan"), report
                )
            except (ValueError, TypeError, KeyError, AttributeError) as exc:
                raise RendererFailure("evidence") from exc
            check_cancelled(cancel)
        return CustomerBriefingOutcome(
            "included", None, CustomerBriefingArtifacts(pdf, evidence)
        )
    except RendererFailure as exc:
        return CustomerBriefingOutcome("omitted", exc.code, None)
    except (OSError, ValueError):
        return CustomerBriefingOutcome("omitted", "runtime", None)
