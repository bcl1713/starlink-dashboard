"""Owned Python child: prepare immutable inputs and qualified one-leg PDF pages."""

import ctypes
import json
import os
import signal
import sys
import threading
from dataclasses import replace
from pathlib import Path

from filelock import FileLock

from app.mission.exporter.customer_runtime import render_customer_artifacts
from app.mission.exporter.export_cancel import ExportCancelled
from app.mission.exporter.snapshot import prepare_export_snapshot

from .identity import decode_inputs, encode_snapshot


def main():
    # If the coordinator dies, request renderer cleanup rather than orphaning it.
    parent = os.getppid()
    cancel = threading.Event()
    preparing = True

    def stop(*_):
        cancel.set()
        if preparing:
            raise ExportCancelled("Worker cancelled")

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    ctypes.CDLL(None).prctl(1, signal.SIGTERM)
    if os.getppid() != parent:
        cancel.set()
    root, fingerprint = Path(sys.argv[1]), sys.argv[2]
    with FileLock(sys.argv[3]):
        metadata, sources, warnings, number, count = decode_inputs(
            (root / "inputs.json").read_bytes()
        )
        snapshot = replace(
            prepare_export_snapshot(metadata, sources, warnings),
            fingerprint=fingerprint,
            leg_number_offset=number - 1,
            leg_count=count,
        )
        (root / "snapshot.json").write_bytes(encode_snapshot(snapshot))
        preparing = False
        outcome = render_customer_artifacts(snapshot, cancel=cancel)
        if outcome.artifacts:
            (root / "pages.pdf").write_bytes(outcome.artifacts.pdf)
            (root / "evidence.json").write_bytes(outcome.artifacts.evidence)
        (root / "result.json").write_text(
            json.dumps(
                {
                    "included": outcome.status == "included",
                    "warning": outcome.warning_code,
                }
            )
        )


if __name__ == "__main__":
    main()
