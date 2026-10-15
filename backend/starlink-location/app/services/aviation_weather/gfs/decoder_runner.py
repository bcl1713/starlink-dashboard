"""One disposable scientific child; owner lock survives parent loss until exit."""

import ctypes
import json
import os
import resource
import signal
import sys
from pathlib import Path

from app.models.aviation_grid import GfsSelection, RangeRef, SourceBundle, SourceRef

from .decode import decode_bundle
from .grid import normalize_grid


def parent_death_guard(parent_pid):
    if ctypes.CDLL(None, use_errno=True).prctl(1, signal.SIGTERM) != 0:
        raise OSError(ctypes.get_errno(), "Cannot guard scientific owner death")
    if os.getppid() != parent_pid:
        raise SystemExit("Scientific owner already exited")


def main():
    manifest, destination, parent, now_ms = sys.argv[1:]
    parent_death_guard(int(parent))
    resource.setrlimit(resource.RLIMIT_CPU, (120, 130))
    resource.setrlimit(resource.RLIMIT_FSIZE, (256 * 1024**2, 256 * 1024**2))
    path = Path(manifest)
    data = json.loads(path.read_bytes())
    paths = tuple(path.parent / name for name in data["paths"])
    if any(
        not entry.resolve().is_relative_to(path.parent.resolve()) or entry.is_symlink()
        for entry in paths
    ):
        raise ValueError("Scientific child source escapes its owned stage")
    ranges = tuple(
        RangeRef(
            SourceRef(**ref["source"]),
            ref["start"],
            ref["end"],
            ref["quantity"],
            ref["pressure_pa"],
        )
        for ref in data["ranges"]
    )
    bundle = SourceBundle(
        data["run_at_ms"],
        data["lead_seconds"],
        ranges,
        paths,
        tuple(data["hashes"]),
        data["retrieved_at_ms"],
        tuple(data["available_leads"]),
    )
    normalize_grid(
        decode_bundle(bundle),
        GfsSelection.model_validate(data["selection"]),
        Path(destination),
        clock=lambda: int(now_ms) / 1000,
    )


if __name__ == "__main__":
    main()
