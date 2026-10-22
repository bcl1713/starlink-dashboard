"""Offline adapter owner. Accepts Stage 2 drain and Stage 3A browser sink records.

No HTTP or browser launch path exists here. Artifact loaders must return bounded
bytes. Projection never infers an association from equal timestamps or values.
"""

import hashlib
import json
import uuid

import build
from evidence import BrowserProjection, canonical
from host import anchor


def normalize_history(history, *, viewer, request, bundle, segment="measured"):
    return {
        "viewer": viewer,
        "request_id": request,
        "bundle_id": bundle,
        "start": history["start_timestamp_seconds"],
        "end": history["end_timestamp_seconds"],
        "step": history["step_seconds"],
        "series": history["series"],
        **({"rolling_5m": history["rolling_5m"]} if history.get("rolling_5m") else {}),
        "segment": segment,
    }


class Integration:
    def __init__(self, sink, *, role, run, page="p", module_hashes=None):
        self.sink = sink
        self.role = role
        self.run = run
        self.page = page
        self.browser = BrowserProjection(role, run, page)
        self.module_hashes = module_hashes or {}
        self.node_uuid = str(uuid.uuid4())
        self.node_start = str(__import__("time").monotonic_ns())
        self.node_stream = self.node_uuid + "/host"
        self.node_seq = 0
        self.node_identity = None
        self.browser_streams = {}
        self.backend_streams = {}
        self.observer_streams = {}
        self.paint_streams = {}
        self.paint_requests = {}
        self.paint_serial = 0
        self.closed = False

    def backend(self, rows):
        for row in rows:
            if row["emitter"] != "backend" or row["role"] != self.role:
                raise ValueError("backend role/emitter")
            self.backend_streams[row["stream_id"]] = row["seq"]
            self.sink.accept(row)

    def finish_backend(self, stats):
        loss = sum(stats.get(key, 0) for key in ("dropped", "invalid", "failures"))
        if loss or stats.get("buffered") != 0:
            self.sink.failed = True
        for stream, seq in self.backend_streams.items():
            self.sink.summary(
                stream, last_seq=seq, dropped=loss, complete=stats.get("buffered") == 0
            )

    def _v1(self, kind, data, *, mono=None, clock=None, op=None):
        # Data-only records originate in the collector; no browser/native TID claim.
        try:
            accepted = self.sink.v1.emit(
                kind, data, mono_ns=mono, clock_id=clock or self.node_uuid, op_id=op
            )
            if not accepted:
                self.sink.failed = True
            return accepted
        except (ValueError, OSError):
            self.sink.failed = True
            self.sink.dropped += 1
            return False

    def browser_record(self, row, *, load=None):
        if self.closed:
            raise RuntimeError("closed adapter")
        raw = row.get("event")
        artifact = None
        if raw is not None:
            if row.get("sha256"):
                if load is None:
                    raise ValueError("artifact loader unavailable")
                body = load(row["artifact"])
                if (
                    len(body) > 2097152
                    or hashlib.sha256(body).hexdigest() != row["sha256"]
                ):
                    raise ValueError("browser artifact identity/budget")
                complete = json.loads(body)
                if {k: v for k, v in complete.items() if k != "detail"} != raw:
                    raise ValueError("browser header/artifact identity")
                raw = complete
                artifact = self.sink.artifact(body)
            page = raw["stream"].split("/")[1]
            if (
                page not in ("p", "p1", "p2", "viewer1", "viewer2")
                and not page == self.page
            ):
                raise ValueError("unregistered browser page")
            browser = BrowserProjection(self.role, self.run, page)
            event = browser.event(raw, artifact=artifact)
            self.browser_streams[event["stream_id"]] = event["seq"]
            self.sink.accept(event)
            detail = raw.get("detail", {})
            request = raw.get("op")
            if (
                raw["phase"] == "app.parse_available"
                and request
                and detail.get("history")
            ):
                self._v1(
                    "history",
                    normalize_history(
                        detail["history"],
                        viewer=page,
                        request=request,
                        bundle=detail["bundle"],
                    ),
                    op=request,
                )
            if raw["phase"] == "plot.commit":
                # Exact actual retained input and committed arrays are mandatory.
                required = (
                    "retained",
                    "projection",
                    "plot",
                    "accepted",
                    "acceptedRequest",
                    "metric",
                    "commit",
                )
                for name, snap in row.get("snapshots", {}).items():
                    if (
                        name not in ("retained", "projection", "plot")
                        or name not in detail
                        or not snap
                        or load is None
                    ):
                        self.sink.failed = True
                        raise ValueError("snapshot unavailable")
                    try:
                        data = load(snap["artifact"])
                    except (OSError, KeyError, ValueError):
                        self.sink.failed = True
                        raise ValueError("snapshot reference unavailable") from None
                    if (
                        len(data) > 2097152
                        or hashlib.sha256(data).hexdigest() != snap["sha256"]
                        or json.loads(data) != detail[name]
                    ):
                        self.sink.failed = True
                        raise ValueError("snapshot hash/content mismatch")
                    if self.sink.artifact(data)["state"] != "available":
                        raise ValueError("snapshot storage unavailable")
                if (
                    not all(k in detail for k in required)
                    or not artifact
                    or detail["acceptedRequest"] != request
                    or not self.module_hashes
                ):
                    self._v1(
                        "coverage",
                        {
                            "boundary": "chart.input",
                            "available": False,
                            "reason": "missing actual retained/plot/provenance/module hashes",
                        },
                    )
                    return
                if not all(
                    name in row.get("snapshots", {})
                    for name in ("retained", "projection", "plot")
                ):
                    self.sink.failed = True
                    raise ValueError("snapshot unavailable")
                data = detail["plot"]["data"]
                scales = detail["plot"]["scales"]["x"]
                projection = normalize_history(
                    detail["retained"],
                    viewer=page,
                    request=request,
                    bundle=detail["accepted"],
                )
                self._v1(
                    "chart",
                    {
                        "viewer": page,
                        "request_id": request,
                        "bundle_id": detail["accepted"],
                        "series": detail["metric"],
                        "segment": "measured",
                        "times": data[0],
                        "traces": dict(
                            zip(("max", "min", "avg", "observed"), data[1:])
                        ),
                        "viewport": [scales["min"], scales["max"]],
                        "visible_gaps": None,
                        "module_hashes": self.module_hashes,
                        "paint_evidence": None,
                        "input_stage": "plot",
                        "log_floor": detail.get("logFloor"),
                        "projection_input": projection,
                    },
                    op=request,
                )
            return
        phase = {
            "browser.response": "browser.headers",
            "browser.finished": "browser.end",
        }.get(row.get("phase"), row.get("phase"))
        if phase not in (
            "browser.request",
            "browser.headers",
            "browser.end",
            "browser.failed",
            "paint.request",
            "paint.artifact",
        ):
            raise ValueError("unsupported host browser event")
        page = row.get("page_id", self.page)
        supplied = row.get("host_identity")
        if not supplied:
            raise ValueError("Node emitter identity unavailable")
        if self.node_identity is not None and supplied != self.node_identity:
            raise ValueError("Node restart requires new adapter")
        self.node_identity = supplied
        self.node_stream = supplied["process_uuid"] + "/node"
        self.node_seq += 1
        identity = {"viewer_id": page}
        if row.get("requestId"):
            identity["request_id"] = row["requestId"]
        if phase == "paint.artifact":
            reference = None
            if row.get("sha256") and row.get("artifact") and load is not None:
                try:
                    body = load(row["artifact"])
                except (OSError, KeyError, ValueError):
                    self.sink.failed = True
                    raise ValueError("PNG reference unavailable") from None
                if (
                    len(body) > 2097152
                    or hashlib.sha256(body).hexdigest() != row["sha256"]
                ):
                    self.sink.failed = True
                    raise ValueError("PNG hash/body budget")
                reference = self.sink.artifact(body)
            if reference and reference["state"] == "available":
                identity["artifact_sha256"] = reference["sha256"]
            else:
                identity["artifact_sha256"] = None
        event = {
            "schema": build.SCHEMA,
            "version": 1,
            "role": self.role,
            "emitter": "node",
            "run_id": self.run,
            "stream_id": self.node_stream,
            "seq": self.node_seq,
            "process_uuid": supplied["process_uuid"],
            "pid": supplied["pid"],
            "tid": None,
            "process_start_id": supplied["process_start_id"],
            "thread_start_id": None,
            "clock_id": supplied["clock_id"],
            "mono_ns": row["host_received_ns"],
            "thread_cpu_ns": None,
            "op_id": row.get("requestId") or f"{self.page}/host/{self.node_seq}",
            "parent_op_id": None,
            "span_id": None,
            "operation_type": (
                "presentation" if phase.startswith("paint.") else "history"
            ),
            "phase": phase,
            "outcome": row.get("outcome", "ok"),
            "identity": identity,
            "unavailable": {},
        }
        if phase.startswith("paint."):
            key = (page, row.get("panel"), row.get("commit"), row.get("started_ns"))
            if phase == "paint.request":
                if key in self.paint_requests or len(self.paint_requests) >= 8:
                    self.sink.failed = True
                    raise ValueError("paint request identity/budget")
                self.paint_serial += 1
                stream = self.node_stream + "/paint" + str(self.paint_serial)
                self.paint_requests[key] = stream
                event.update(
                    stream_id=stream,
                    seq=1,
                    mono_ns=row["started_ns"],
                    op_id=f"{page}/paint/{self.paint_serial}",
                )
                self.paint_streams[stream] = 1
            else:
                stream = self.paint_requests.pop(key, None)
                if stream:
                    event.update(
                        stream_id=stream,
                        seq=2,
                        mono_ns=row["received_ns"],
                        op_id=f'{page}/paint/{stream.rsplit("paint",1)[1]}',
                    )
                    self.paint_streams[stream] = 2
                else:
                    self.paint_serial += 1
                    stream = self.node_stream + "/paint" + str(self.paint_serial)
                    event.update(
                        stream_id=stream,
                        seq=1,
                        mono_ns=row["received_ns"],
                        op_id=f"{page}/paint/{self.paint_serial}",
                        outcome="unavailable",
                    )
                    self.paint_streams[stream] = 1
                if identity.get("artifact_sha256") is None:
                    event["outcome"] = "unavailable"
                    event["unavailable"] = {
                        "artifact_sha256": "missing verified compositor artifact"
                    }
            self.node_seq -= 1
        self.sink.accept(event)

    def finish_browser(self, summary):
        lost = summary.get("lost", 0)
        complete = (
            summary.get("closed") is True
            and not summary.get("failed")
            and not any(
                summary.get(k, 0)
                for k in (
                    "active",
                    "pending",
                    "jobs",
                    "bindingJobs",
                    "ownedOperations",
                    "assemblies",
                    "bytes",
                )
            )
        )
        if lost or not complete or self.paint_requests:
            self.sink.failed = True
            complete = False
        for stream, seq in self.browser_streams.items():
            self.sink.summary(stream, last_seq=seq, dropped=lost, complete=complete)
        if self.node_seq:
            self.sink.summary(
                self.node_stream,
                last_seq=self.node_seq,
                dropped=lost,
                complete=complete,
            )
        for stream, seq in self.paint_streams.items():
            self.sink.summary(stream, last_seq=seq, dropped=lost, complete=complete)

    def source_record(self, row):
        raw = row["event"]
        if raw.get("run", self.run) != self.run:
            raise ValueError("observer run mismatch")
        node = row["host_identity"]
        stream = node["process_uuid"] + "/observer"
        identity = {"request_id": raw["op"]}
        if raw.get("skipped"):
            identity["branch"] = "skipped:" + str(raw["skipped"])
        if raw.get("late_ns"):
            identity["observation_timestamp"] = raw["late_ns"]
        # Scheduling fields are stored in hashed raw records by collect.mjs;
        # observation_timestamp is reserved for source acquisition, never late-wake.
        identity.pop("observation_timestamp", None)
        event = {
            "schema": build.SCHEMA,
            "version": 1,
            "role": self.role,
            "emitter": "observer",
            "run_id": self.run,
            "stream_id": stream,
            "seq": raw["seq"],
            "process_uuid": node["process_uuid"],
            "pid": node["pid"],
            "tid": None,
            "process_start_id": node["process_start_id"],
            "thread_start_id": None,
            "clock_id": node["clock_id"],
            "mono_ns": raw["mono_ns"],
            "thread_cpu_ns": None,
            "op_id": raw["op"],
            "parent_op_id": None,
            "span_id": None,
            "operation_type": "source_observer",
            "phase": raw["phase"],
            "outcome": raw.get("outcome", "ok"),
            "identity": identity,
            "unavailable": {},
        }
        self.observer_streams[stream] = raw["seq"]
        self.sink.accept(event)

    def finish_source(self, summary):
        if summary.get("failed") or not summary.get("closed"):
            self.sink.failed = True
        for stream, seq in self.observer_streams.items():
            self.sink.summary(
                stream,
                last_seq=seq,
                dropped=int(summary.get("failed", False)),
                complete=summary.get("closed", False),
            )

    def resources(self, snapshot):
        self._v1("resource", {"files": snapshot["files"]})
        return self.sink.artifact(canonical(snapshot))

    def clock_anchor(self, **kwargs):
        value = anchor(self.node_uuid, **kwargs)
        self._v1(
            "anchor",
            {"utc_ns": value["utc_ns"], "uncertainty_ns": value["uncertainty_ns"]},
            mono=value["mono_ns"],
            clock=self.node_uuid,
        )
        return value
