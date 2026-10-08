"""Catch lost final IDs, wrong route timing/cache inputs and leaking renderers."""

import io
import json
import signal
import subprocess
import sys
import time
from dataclasses import replace

import psutil
import pytest
from PIL import Image

from app.mission.exporter import trial_maps as maps
from app.mission.exporter.snapshot import ExportSnapshot
from app.mission.exporter.snapshot_inputs import canonical_json
from app.mission.exporter.trial_projection import project_trial_leg
from tests.unit.customer_briefing_fixtures import fixture, snapshot


def mission(name="f02"):
    leg = snapshot(fixture(name))
    captured = ExportSnapshot("fixture", "revision", b"{}", (leg,), (), ())
    return captured, project_trial_leg(leg)


def test_final_interval_markers_use_exact_timed_positions_and_skipped_numbers():
    captured, leg = mission()
    raw, notes = maps.build_map_input(captured.legs[0], leg)
    assert not notes
    assert [m["label"] for m in raw["markers"]] == ["1", "2", "3", "4", "5", "7"]
    assert [m["id"] for m in raw["markers"]] == [
        f"f02-window-{n:03d}" for n in (1, 2, 3, 4, 5, 7)
    ]
    assert [raw["route"][m["routeIndex"]]["timestamp"] for m in raw["markers"]] == [
        "2026-10-07T08:00:00Z",
        "2026-10-07T08:10:00Z",
        "2026-10-07T08:15:00Z",
        "2026-10-07T09:30:00Z",
        "2026-10-07T11:00:00Z",
        "2026-10-07T13:45:00Z",
    ]
    assert raw["referenceUtc"] == "2026-10-07T08:00:00Z"


def test_markers_interpolate_across_dateline_without_greenwich_detour():
    captured, leg = mission("f01")
    route = json.loads(captured.legs[0].effective_route_json)
    route["points"][0].update(latitude=0, longitude=170)
    route["points"][-1].update(latitude=0, longitude=-170)
    changed = replace(captured.legs[0], effective_route_json=canonical_json(route))
    raw, _ = maps.build_map_input(changed, leg)
    assert all(abs(p["longitude"]) >= 170 for p in raw["route"])


def test_trial_map_key_effective_inputs():
    captured, leg = mission()
    raw, _ = maps.build_map_input(captured.legs[0], leg)
    key = maps.map_cache_key(captured, leg, raw, "runtime-a")
    mutations = [
        replace(leg, leg_id="other-leg"),
        replace(leg, intervals=leg.intervals[:-1]),
    ]
    assert all(
        maps.map_cache_key(captured, changed, raw, "runtime-a") != key
        for changed in mutations
    )
    assert maps.map_cache_key(captured, leg, raw, "runtime-b") != key
    for field, value in [
        ("referenceUtc", "2026-10-08T08:00:00Z"),
        ("markers", []),
        ("framingVersion", "next"),
    ]:
        assert (
            maps.map_cache_key(captured, leg, {**raw, field: value}, "runtime-a") != key
        )
    moved = json.loads(json.dumps(raw))
    moved["route"][0]["longitude"] += 1
    assert maps.map_cache_key(captured, leg, moved, "runtime-a") != key
    changed_departure = replace(captured, fingerprint="new-planned-departure")
    assert maps.map_cache_key(changed_departure, leg, raw, "runtime-a") != key


@pytest.mark.parametrize("failure", ["startup", "texture", "context-loss", "timeout"])
def test_trial_map_deadline_fallback_and_cleanup(tmp_path, monkeypatch, failure):
    captured, leg = mission()
    # Real subprocess boundary: fail before PNG publication or hang with a
    # detached descendant. Python must stop/reap it and delete request files.
    driver = tmp_path / "driver.py"
    pidfile = tmp_path / "child.pid"
    driver.write_text(
        "import subprocess,sys,time,os\n"
        + (
            f"p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],start_new_session=True)\nopen({str(pidfile)!r},'w').write(str(p.pid))\ntime.sleep(60)\n"
            if failure == "timeout"
            else "sys.exit(1)\n"
        )
    )
    monkeypatch.setattr(
        maps, "_renderer_command", lambda *args: [sys.executable, str(driver)]
    )
    monkeypatch.setattr(maps, "_runtime_identity", lambda: "unit-test")
    monkeypatch.setattr(maps.tempfile, "tempdir", str(tmp_path))
    started = time.monotonic()
    result = maps.render_trial_maps(captured, (leg, leg), budget_seconds=1.5)
    assert time.monotonic() - started < 5
    assert len(result) == 2
    for rendered in result:
        assert rendered.status == "static"
        assert rendered.label == "Overview map unavailable — static route fallback"
        assert rendered.warnings
        assert rendered.views
        png = Image.open(io.BytesIO(rendered.views[0].png))
        assert png.size == (1920, 1080)
        assert len(png.getcolors(1920 * 1080)) > 1
    if pidfile.exists():
        pid = int(pidfile.read_text())
        assert (
            not psutil.pid_exists(pid)
            or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
        )
    assert not list(tmp_path.glob("trial-map-*"))


def test_missing_route_has_explanatory_card_and_never_starts_browser(
    tmp_path, monkeypatch
):
    captured, leg = mission("f10")
    captured = replace(
        captured, legs=(replace(captured.legs[0], effective_route_json=None),)
    )
    monkeypatch.setattr(
        maps,
        "_renderer_command",
        lambda *args: pytest.fail("No browser for missing route"),
    )
    result = maps.render_trial_maps(captured, (leg,))
    assert result[0].status == "unavailable"
    assert result[0].label == "Route map unavailable"
    assert result[0].reason
    assert result[0].endpoints


def test_zero_budget_skips_browser_and_static_stage_is_bounded(monkeypatch):
    captured, leg = mission()
    monkeypatch.setattr(
        maps, "_renderer_command", lambda *args: pytest.fail("Deadline exhausted")
    )
    result = maps.render_trial_maps(captured, (leg,), budget_seconds=0)
    assert result[0].status == "static"
    assert result[0].warnings


def test_missing_route_timing_never_invents_marker_positions():
    captured, leg = mission()
    route = json.loads(captured.legs[0].effective_route_json)
    route["points"][0]["expected_arrival_time"] = None
    changed = replace(captured.legs[0], effective_route_json=canonical_json(route))
    raw, notes = maps.build_map_input(changed, leg)
    assert raw is None
    assert "timing" in " ".join(notes).lower()


def test_termination_stops_owned_detached_descendants(tmp_path):
    pidfile = tmp_path / "descendant.pid"
    driver = tmp_path / "sleep.py"
    driver.write_text(
        "import subprocess,sys,time\n"
        "p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],start_new_session=True)\n"
        f"open({str(pidfile)!r},'w').write(str(p.pid))\n"
        "time.sleep(60)\n"
    )
    parent = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "from app.mission.exporter.trial_maps import _run_owned;from pathlib import Path;import sys,time;"
                f"_run_owned([sys.executable,{str(driver)!r}],Path({str(tmp_path)!r}),time.monotonic()+60)"
            ),
        ],
        start_new_session=True,
    )
    descendant = None
    try:
        deadline = time.monotonic() + 10
        while not pidfile.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert pidfile.exists()
        descendant = psutil.Process(int(pidfile.read_text()))
        parent.send_signal(signal.SIGTERM)
        parent.wait(timeout=3)
        assert (
            not descendant.is_running() or descendant.status() == psutil.STATUS_ZOMBIE
        )
    finally:
        owned = (
            psutil.Process(parent.pid).children(recursive=True)
            if parent.poll() is None
            else []
        )
        if descendant:
            owned.append(descendant)
        for child in owned:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        if parent.poll() is None:
            parent.kill()
        parent.wait()


def test_static_output_cannot_escape_request_directory(tmp_path, monkeypatch):
    captured, leg = mission()
    identity = "../../escape"
    captured = replace(captured, legs=(replace(captured.legs[0], leg_id=identity),))
    leg = replace(leg, leg_id=identity)
    monkeypatch.setattr(maps.tempfile, "tempdir", str(tmp_path))
    result = maps.render_trial_maps(captured, (leg,), budget_seconds=0)
    assert result[0].status == "static"
    assert not (tmp_path / "escape.png").exists()
