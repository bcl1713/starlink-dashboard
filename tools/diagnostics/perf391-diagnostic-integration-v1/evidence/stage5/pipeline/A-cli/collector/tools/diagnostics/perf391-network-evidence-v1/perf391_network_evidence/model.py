"""Closed, versioned event contract; nanosecond strings preserve JS precision."""

import json
import os
import threading
import time
import uuid
from pathlib import Path

from jsonschema import Draft202012Validator

SCHEMA = json.loads(Path(__file__).with_name("event-schema.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA)
CLOCK = "python-" + uuid.uuid4().hex


def validate(row):
    try:
        json.dumps(row, allow_nan=False)
        VALIDATOR.validate(row)
    except Exception as exc:
        raise ValueError(str(exc)) from exc
    data = row["data"]
    if row["kind"] == "scrape" and (data["state"] == "finite") != (
        data["value"] is not None
    ):
        raise ValueError(
            "finite scrape requires a finite value; missing states require null"
        )
    if row["kind"] in ("chart", "evaluation"):
        times = data["times"]
        if times != sorted(set(times)):
            raise ValueError("array timestamps must increase strictly")
        arrays = (
            data["traces"].values()
            if row["kind"] == "chart"
            else [data["values"], data["sample_timestamps"]]
        )
        if any(len(v) != len(times) for v in arrays):
            raise ValueError("timestamp/value array lengths must match")
        if row["kind"] == "chart":
            if len(data["viewport"]) != 2 or data["viewport"][1] <= data["viewport"][0]:
                raise ValueError("positive viewport required")
            intervals = data["visible_gaps"]
            if intervals is not None and any(
                len(v) != 2 or v[1] <= v[0] or (i and intervals[i - 1][1] > v[0])
                for i, v in enumerate(intervals)
            ):
                raise ValueError("paint intervals must be ordered and nonoverlapping")
    return row


def event(
    kind,
    data,
    *,
    mono_ns=None,
    clock_id=CLOCK,
    run_id="offline",
    stream_id="fixture",
    seq=0,
    op_id=None,
    span_id=None,
    thread_cpu_ns=None,
):
    return {
        "schema": "perf391-network-evidence-v1",
        "version": 1,
        "kind": kind,
        "run_id": run_id,
        "stream_id": stream_id,
        "seq": seq,
        "clock_id": clock_id,
        "mono_ns": str(time.monotonic_ns() if mono_ns is None else mono_ns),
        "pid": os.getpid(),
        "tid": threading.get_native_id(),
        "thread_cpu_ns": None if thread_cpu_ns is None else str(thread_cpu_ns),
        "op_id": op_id,
        "span_id": span_id,
        "data": data,
    }
