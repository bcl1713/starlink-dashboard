"""Acceptance-only observation/fault harness; production routes and exporters intact.

No response interception, fabricated success, or alternate export endpoint.
Faults are startup-selected in an isolated container; never shipped in app code.
"""

import json
import os
import time
from pathlib import Path

from app.mission.exporter import trial_maps, trial_pptx, trial_projection
from app.mission.package import __main__ as package
from main import app

__all__ = ["app"]

PROBE = Path("/probe")
PROBE.mkdir(exist_ok=True)
FAULT = os.environ.get("BRIEFING_FAULT", "none")


def emit(kind, value):
    with (PROBE / "stages.jsonl").open("a") as handle:
        handle.write(json.dumps({"stage": kind, "fault": FAULT, **value}) + "\n")


def observe(module, name):
    original = getattr(module, name)

    def measured(*args, **kwargs):
        started = time.monotonic()
        try:
            result = original(*args, **kwargs)
            value = {}
            if name == "capture_export_snapshot":
                value = {
                    "mission_id": result.mission_id,
                    "fingerprint": result.fingerprint,
                    "origins": [leg.preparation_origin for leg in result.legs],
                }
            if name == "render_trial_maps":
                value = {
                    "maps": [
                        {
                            "leg_id": m.leg_id,
                            "status": m.status,
                            "warnings": m.warnings,
                            "views": [v.id for v in m.views],
                            "renderer": (
                                json.loads(m.renderer_evidence_json)
                                if m.renderer_evidence_json
                                else None
                            ),
                        }
                        for m in result
                    ]
                }
            emit(name, {"seconds": round(time.monotonic() - started, 3), **value})
            return result
        except BaseException as error:
            emit(
                name,
                {
                    "seconds": round(time.monotonic() - started, 3),
                    "exception_type": type(error).__name__,
                },
            )
            raise

    setattr(module, name, measured)


for module, name in (
    (package, "capture_export_snapshot"),
    (trial_maps, "render_trial_maps"),
    (trial_pptx, "build_trial_pptx"),
):
    observe(module, name)


def fail(*args, **kwargs):
    raise RuntimeError("acceptance private-token /private/customer " + "x" * 10000)


if FAULT == "projection":
    trial_projection.project_trial_leg = fail
elif FAULT == "invalid-pptx":
    trial_pptx.build_trial_pptx = lambda *args, **kwargs: b"invalid PPTX"
elif FAULT == "browser":
    trial_maps._renderer_command = lambda *a: ["/nonexistent-acceptance-browser"]
elif FAULT in ("texture", "slow"):
    original_command = trial_maps._renderer_command
    trial_maps._renderer_command = lambda *a: [*original_command(*a), FAULT]
elif FAULT == "deadline":
    original_maps = trial_maps.render_trial_maps
    trial_maps.render_trial_maps = lambda snapshot, legs: original_maps(
        snapshot, legs, budget_seconds=0
    )
elif FAULT == "all-maps":
    trial_maps._run_owned = lambda *args, **kwargs: False
elif FAULT != "none":
    raise ValueError("unknown acceptance fault")
