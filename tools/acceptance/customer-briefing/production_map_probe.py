"""Copied into an offline final backend image by map_production.py.

Uses actual Task 2 projections and Task 3B entry point, including fallback,
private inputs, PNG validation and cleanup. It never starts the application.
"""

import json
import hashlib
import os
from dataclasses import asdict
from pathlib import Path
import sys
import time
import subprocess
import signal
import shutil

import psutil

from app.mission.exporter import trial_maps
from app.mission.exporter.snapshot import ExportSnapshot
from app.mission.exporter.trial_projection import project_trial_leg
from tests.unit.customer_briefing_fixtures import fixture, snapshot


def parent_death_check(output, inputs):
    stage = Path("/tmp/parent-death-stage")
    stage.mkdir()
    input_path = stage / "input.json"
    input_path.write_text(json.dumps({"legs": inputs}))
    command = [*trial_maps._renderer_command(input_path, stage), "slow"]
    owner = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "from app.mission.exporter.trial_maps import _run_owned;from pathlib import Path;import time;"
            f"_run_owned({command!r},Path({str(stage)!r}),time.monotonic()+60)",
        ],
        start_new_session=True,
    )
    owned = []
    try:
        deadline = time.monotonic() + 10
        browser = None
        while time.monotonic() < deadline:
            try:
                ownership = json.loads((stage / "ownership.json").read_text())
                browser = ownership.get("browserPid")
                if browser:
                    break
            except (OSError, ValueError):
                pass
            time.sleep(0.02)
        assert browser, "Browser did not start for parent-death check"
        owned = psutil.Process(owner.pid).children(recursive=True)
        owner.send_signal(signal.SIGKILL)
        owner.wait(timeout=2)
        deadline = time.monotonic() + 5
        while (
            any(p.is_running() and p.status() != psutil.STATUS_ZOMBIE for p in owned)
            and time.monotonic() < deadline
        ):
            time.sleep(0.02)
        alive = [
            p.pid
            for p in owned
            if p.is_running() and p.status() != psutil.STATUS_ZOMBIE
        ]
        renderer = (
            json.loads((stage / "result.json").read_text())
            if (stage / "result.json").exists()
            else None
        )
        verified = (
            not alive
            and renderer
            and all(
                renderer["cleanup"][key]
                for key in ("browserExited", "listenerClosed", "contextsClosed")
            )
        )
        (output / "result.json").write_text(
            json.dumps(
                {
                    "status": "terminated",
                    "views": [],
                    "results": [],
                    "cleanupVerified": bool(verified),
                    "parentDeathVerified": bool(verified),
                    "survivors": alive,
                    "renderer": renderer,
                },
                indent=2,
            )
        )
        assert verified, "Parent death left browser/listener descendants alive"
    finally:
        if owner.poll() is None:
            owned = psutil.Process(owner.pid).children(recursive=True)
            owner.terminate()
            owner.wait(timeout=2)
        for process in owned:
            if process.is_running() and process.status() != psutil.STATUS_ZOMBIE:
                process.terminate()
        _, alive = psutil.wait_procs(owned, timeout=1)
        for process in alive:
            if process.status() != psutil.STATUS_ZOMBIE:
                process.kill()
        psutil.wait_procs(alive, timeout=1)
        shutil.rmtree(stage)


def main():
    output = Path("/tmp/evidence")
    output.mkdir()
    fault = sys.argv[1] if len(sys.argv) > 1 else None
    captured_legs = tuple(snapshot(leg) for leg in fixture("f08")["legs"])
    captured = ExportSnapshot(
        "f08-map-final", "f08-task2-final", b"{}", captured_legs, (), ()
    )
    projected = tuple(project_trial_leg(leg) for leg in captured_legs)
    inputs = [
        trial_maps.build_map_input(leg, trial)[0]
        for leg, trial in zip(captured_legs, projected)
    ]
    expected_markers = [
        [
            {
                "id": interval.id,
                "label": str(interval.window_number),
                "start": interval.start_time.isoformat().replace("+00:00", "Z"),
            }
            for interval in leg.coordination_rows
        ]
        for leg in projected
    ]
    for raw, expected in zip(inputs, expected_markers):
        actual = [
            {
                "id": marker["id"],
                "label": marker["label"],
                "start": raw["route"][marker["routeIndex"]]["timestamp"],
            }
            for marker in raw["markers"]
        ]
        assert actual == expected, "Final projection IDs/positions changed"
    if fault == "parent-death":
        parent_death_check(output, inputs)
        return
    if fault:
        command = trial_maps._renderer_command
        trial_maps._renderer_command = lambda *args: [*command(*args), fault]
    before = time.monotonic()
    results = trial_maps.render_trial_maps(
        captured, projected, budget_seconds=3 if fault == "slow" else 60
    )
    renderer = (
        json.loads(results[0].renderer_evidence_json)
        if results[0].renderer_evidence_json
        else None
    )
    views = []
    for result in results:
        for view in result.views:
            name = view.id.replace("/", "-") + ".png"
            (output / name).write_bytes(view.png)
            views.append({"id": view.id, "filename": name})
    processes = psutil.Process().children(recursive=True)
    alive = [
        {"pid": p.pid, "name": p.name()}
        for p in processes
        if p.status() != psutil.STATUS_ZOMBIE
    ]
    private_paths = list(Path("/tmp").glob("trial-map-*"))
    summary = {
        "backendSourceDigest": hashlib.sha256(
            Path(trial_maps.__file__).read_bytes()
        ).hexdigest(),
        "status": (
            "primary"
            if all(result.status == "primary" for result in results)
            else "fallback"
        ),
        "pythonStageSeconds": time.monotonic() - before,
        "uid": os.getuid(),
        "inputs": inputs,
        "expectedMarkers": expected_markers,
        "results": [
            {
                **asdict(result),
                "views": [view.id for view in result.views],
                "renderer_evidence_json": None,
            }
            for result in results
        ],
        "views": views,
        "renderer": renderer,
        "cleanupVerified": not alive and not private_paths,
        "survivors": alive,
        "privatePaths": [str(p) for p in private_paths],
    }
    (output / "result.json").write_text(json.dumps(summary, indent=2))
    if fault:
        assert all(result.status == "static" for result in results), summary
        assert renderer and renderer["status"] == "fallback", summary
        assert renderer["cleanup"] == {
            "listenerClosed": True,
            "browserExited": True,
            "contextsClosed": True,
            "errors": [],
        }
    else:
        assert summary["status"] == "primary", summary
        assert [view["id"] for view in views] == [
            "f08-short/view-1",
            "f08-polar-dateline/view-1",
            "f08-spanning/view-1",
            "f08-spanning/view-2",
            "f08-spanning/view-3",
        ]
    assert summary["cleanupVerified"], summary
    print(
        json.dumps(
            {
                "status": summary["status"],
                "seconds": summary["pythonStageSeconds"],
                "views": [v["id"] for v in views],
            }
        )
    )


if __name__ == "__main__":
    main()
