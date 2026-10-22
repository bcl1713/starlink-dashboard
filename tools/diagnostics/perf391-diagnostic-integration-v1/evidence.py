"""Bounded integration sink and loss-aware projection into immutable #407.

The v1 Recorder owns queue/drain/artifacts/final summary. Projection adds a
source-preserving enqueue using its existing limits, lock and queue format;
v1's generic emit() would stamp the collector's own PID/TID/CPU on source rows.
"""

import hashlib
import json
import math
import threading
import uuid
from collections import deque
from pathlib import Path

import build
import contract


def canonical(row):
    return json.dumps(
        row, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(65536):
            digest.update(block)
    return digest.hexdigest()


class Evidence:
    def __init__(
        self,
        root,
        collector,
        *,
        run,
        max_events=4096,
        max_bytes=8388608,
        max_disk=268435456,
    ):
        if (
            not 1 <= max_events <= 4096
            or not 1 <= max_bytes <= 8388608
            or not 16384 <= max_disk <= 268435456
        ):
            raise ValueError("evidence budgets")
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=False)
        self.collector = collector
        self.run = run
        self.closed = False
        self.failed = False
        self.max_events = max_events
        self.max_bytes = max_bytes
        self.max_disk = max_disk
        # Reserve half for sidecar and finalization; the v1 recorder accounts for its own half.
        self.v1 = collector.record.Recorder(
            self.root / "v1",
            run_id=run,
            max_events=max_events,
            max_bytes=max_bytes,
            max_disk_bytes=max_disk // 2,
            max_event_bytes=1048576,
        )
        self.file = (self.root / "integration.jsonl").open("xb")
        self.queue = deque()
        self.pending_bytes = 0
        self.disk_bytes = 0
        self.dropped = 0
        self.high_water = 0
        self.summaries = {}
        self.streams = {}
        self.lock = threading.RLock()
        self.max_streams = min(4096, max_disk // 4096)
        self.artifacts = 0
        self.validator = contract.StreamValidator(self.max_streams)

    def accept(self, row):
        with self.lock:
            if self.closed:
                raise RuntimeError("closed evidence")
            try:
                self.validator.accept(row)
                if row["run_id"] != self.run:
                    raise ValueError("run identity")
                raw = canonical(row) + b"\n"
                if (
                    len(self.streams) >= self.max_streams
                    and row["stream_id"] not in self.streams
                ):
                    raise ValueError("stream budget")
                self.streams[row["stream_id"]] = max(
                    row["seq"], self.streams.get(row["stream_id"], 0)
                )
                if (
                    self.failed
                    or len(raw) > 1048576
                    or len(self.queue) >= self.max_events
                    or self.pending_bytes + len(raw) > self.max_bytes
                    or self.disk_bytes + self.pending_bytes + len(raw)
                    > self.max_disk // 4
                ):
                    self.dropped += 1
                    return False
                self.queue.append((row, raw))
                self.pending_bytes += len(raw)
                self.high_water = max(self.high_water, len(self.queue))
                return True
            except (ValueError, contract.ContractError):
                self.dropped += 1
                self.failed = True
                return False

    def _project(self, row):
        if row["phase"] not in contract.CONTRACT["v1_boundary_phases"]:
            return
        if row["tid"] is None:
            # v1 mandates an integer native TID. Browser TIDs remain unavailable;
            # do not insert Node's TID or zero to force schema compatibility.
            return
        rec = self.v1
        rec.seq += 1
        event = self.collector.model.event(
            "boundary",
            {
                "name": row["phase"],
                "identity": row["identity"],
                "outcome": row["outcome"],
            },
            mono_ns=row["mono_ns"],
            clock_id=row["clock_id"],
            run_id=row["run_id"],
            stream_id=rec.stream_id,
            seq=rec.seq,
            op_id=row["op_id"],
            span_id=row["span_id"],
            thread_cpu_ns=row["thread_cpu_ns"],
        )
        event.update(pid=row["pid"], tid=row["tid"])
        self.collector.model.validate(event)
        raw = canonical(event) + b"\n"
        with rec.lock:
            if (
                len(rec.pending) >= rec.max_events
                or len(raw) > rec.max_event_bytes
                or rec.pending_bytes + len(raw) > rec.max_bytes
                or rec.disk_bytes + rec.pending_bytes + len(raw)
                > rec.max_disk_bytes - rec.RESERVE
            ):
                rec.dropped_events += 1
                self.failed = True
                return
            rec.pending.append(raw)
            rec.pending_bytes += len(raw)

    def _write(self, raw):
        written = self.file.write(raw)
        if written != len(raw):
            raise OSError("short evidence write")

    def drain(self):
        with self.lock:
            if self.failed and not self.queue:
                return False
            try:
                while self.queue:
                    row, raw = self.queue[0]
                    self._write(raw)
                    self.disk_bytes += len(raw)
                    self._project(row)
                    self.queue.popleft()
                    self.pending_bytes -= len(raw)
                self.file.flush()
                self.v1.drain()
                return True
            except (OSError, ValueError):
                self.failed = True
                self.dropped += len(self.queue)
                self.queue.clear()
                self.pending_bytes = 0
                return False

    def artifact(self, body):
        with self.lock:
            if self.closed:
                raise RuntimeError("closed evidence")
            if len(body) > 2097152 or self.artifacts >= min(64, self.max_disk // 4096):
                self.v1.dropped_bodies += 1
                self.failed = True
                return {
                    "state": "unavailable",
                    "path": None,
                    "sha256": None,
                    "bytes": len(body),
                    "reason": "body_limit",
                }
            try:
                result = self.v1.artifact(body)
                if result["state"] == "available":
                    self.artifacts += 1
                if result["state"] != "available":
                    self.failed = True
                return result
            except OSError:
                self.failed = True
                self.v1.dropped_bodies += 1
                return {
                    "state": "unavailable",
                    "path": None,
                    "sha256": None,
                    "bytes": len(body),
                    "reason": "disk_error",
                }

    def summary(self, stream_id, *, last_seq, dropped, complete):
        if (
            type(last_seq) is not int
            or last_seq < 0
            or type(dropped) is not int
            or dropped < 0
            or type(complete) is not bool
        ):
            raise ValueError("invalid stream summary")
        if len(self.summaries) >= self.max_streams and stream_id not in self.summaries:
            raise ValueError("summary budget")
        if stream_id in self.summaries:
            raise ValueError("duplicate final summary")
        self.summaries[stream_id] = {
            "stream_id": stream_id,
            "last_seq": last_seq,
            "dropped": dropped,
            "complete": complete,
        }

    def close(self):
        with self.lock:
            if self.closed:
                return self.result
            self.drain()
            missing = [
                s
                for s, seq in self.streams.items()
                if s not in self.summaries
                or self.summaries[s]["last_seq"] != seq
                or not self.summaries[s]["complete"]
                or self.summaries[s]["dropped"]
            ]
            if set(self.summaries) != set(self.streams):
                self.failed = True
            try:
                self.v1.close(
                    "integration_failed"
                    if self.failed or missing or self.dropped
                    else "closed"
                )
            except OSError:
                self.failed = True
            finally:
                self.file.close()
                self.closed = True
            self.result = {
                "schema": "perf391-integration-summary-v1",
                "version": 1,
                "complete": not (
                    self.failed
                    or missing
                    or self.dropped
                    or self.v1.dropped_events
                    or self.v1.dropped_bodies
                ),
                "dropped": self.dropped,
                "v1_dropped": self.v1.dropped_events,
                "dropped_artifacts": self.v1.dropped_bodies,
                "missing_summaries": missing,
                "streams": list(self.summaries.values()),
                "high_water": self.high_water,
                "sidecar_bytes": self.disk_bytes,
                "v1_bytes": self.v1.disk_bytes,
            }
            try:
                summary_raw = canonical(self.result) + b"\n"
                if len(summary_raw) > self.max_disk // 8:
                    raise OSError("summary budget")
                (self.root / "summary.json").write_bytes(summary_raw)
                hashes = {
                    p.relative_to(self.root).as_posix(): file_hash(p)
                    for p in sorted(self.root.rglob("*"))
                    if p.is_file() and p.name != "SHA256SUMS.json"
                }
                hash_raw = canonical(hashes) + b"\n"
                if len(hash_raw) > self.max_disk // 8:
                    raise OSError("hash inventory budget")
                (self.root / "SHA256SUMS.json").write_bytes(hash_raw)
            except OSError:
                self.result["complete"] = False
                self.result["finalization_unavailable"] = "disk_error"
            return self.result


class BrowserProjection:
    def __init__(self, role, run, page):
        self.role, self.run, self.page = role, run, page

    def event(self, raw, *, artifact=None):
        if raw["run"] != self.run:
            raise ValueError("browser run")
        parts = raw["stream"].split("/")
        if (
            len(parts) != 3
            or parts[:2] != [self.run, self.page]
            or raw["clock"] != f"browser/{self.page}/{parts[2]}"
        ):
            raise ValueError("browser document identity")
        phase = raw["phase"]
        detail = raw.get("detail", {})
        mapped = {
            "query.begin": "probe.failure",
            "react.mount": "probe.failure",
            "react.unmount": "probe.failure",
            "probe.summary": "probe.failure",
        }
        phase = mapped.get(phase, phase)
        if phase not in contract.CONTRACT["phases"]:
            raise ValueError("unsupported browser phase")
        mono = raw["monotonic_ms"]
        if not isinstance(mono, (int, float)) or not math.isfinite(mono) or mono < 0:
            raise ValueError("browser clock")
        identity = {"viewer_id": self.page, "document_id": parts[2]}
        for src, dest in [
            ("bundle", "history_token"),
            ("accepted", "history_token"),
            ("retainedId", "retained_token"),
            ("commit", "plot_token"),
        ]:
            if isinstance(detail.get(src), str):
                identity[dest] = detail[src]
        if raw.get("op"):
            identity["request_id"] = raw["op"]
        if artifact and artifact.get("state") == "available":
            identity["artifact_sha256"] = artifact["sha256"]
        unavailable = {}
        outcome = raw.get("outcome", "ok")
        if phase == "plot.commit" and not artifact:
            outcome = "unavailable"
            identity["artifact_sha256"] = None
            unavailable["artifact_sha256"] = "missing committed actual input artifact"
        process = str(uuid.uuid5(uuid.NAMESPACE_URL, raw["stream"]))
        row = {
            "schema": build.SCHEMA,
            "version": 1,
            "role": self.role,
            "emitter": "browser",
            "run_id": self.run,
            "stream_id": raw["stream"],
            "seq": raw["seq"],
            "process_uuid": process,
            "pid": 0,
            "tid": None,
            "process_start_id": parts[2],
            "thread_start_id": None,
            "clock_id": raw["clock"],
            "mono_ns": str(int(mono * 1000000)),
            "thread_cpu_ns": None,
            "op_id": raw.get("op") or f'{self.page}/{parts[2]}/e{raw["seq"]}',
            "parent_op_id": None,
            "span_id": None,
            "operation_type": (
                "presentation"
                if phase.startswith(("plot.", "paint.", "react.", "history."))
                else "history"
            ),
            "phase": phase,
            "outcome": outcome,
            "identity": identity,
            "unavailable": unavailable,
        }
        contract.validate_event(row)
        return row
