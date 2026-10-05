"""Browser measurements preserve bounded probes and explicit phase semantics."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
JOURNEY = ROOT / "tools/acceptance/journeys/overview-history-performance.mjs"
PROBE = ROOT / "tools/acceptance/journeys/overview-history-probe.mjs"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(
    NODE is None, reason="Node is required for browser tooling contracts"
)


def check_arguments(*changes):
    return subprocess.run(
        [
            NODE,
            str(JOURNEY),
            "--session",
            "http://127.0.0.1:9222",
            "--origin",
            "http://127.0.0.1:15224",
            "--artifacts",
            "/tmp/overview-history-test",
            "--cadence",
            "1",
            "--viewers",
            "2",
            "--window",
            "1800",
            "--warmup-seconds",
            "300",
            "--duration-seconds",
            "3600",
            *changes,
            "--check",
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_browser_measurement_arguments_distinguish_timer_and_duration():
    result = check_arguments()
    assert result.returncode == 0, result.stderr
    options = json.loads(result.stdout)
    assert options["viewport"] == [1920, 1080]
    assert options["dpr"] == 1
    assert options["viewers"] == 2
    assert options["configured_interval_seconds"] == 1
    assert options["requested_measured_seconds"] == 3600
    assert options["warmup_seconds"] == 300


@pytest.mark.parametrize(
    "changes",
    [
        ("--origin", "https://example.com"),
        ("--duration-seconds", "0"),
        ("--viewers", "3"),
        ("--cadence", "2"),
        ("--window", "-1"),
        ("--unknown", "value"),
    ],
)
def test_invalid_browser_measurement_inputs_are_rejected(changes):
    result = check_arguments(*changes)
    assert result.returncode != 0
    assert "invalid" in result.stderr


def test_browser_probe_keeps_only_bounded_counters_and_preserves_json_results():
    script = f"""import {{installOverviewHistoryProbe}} from {json.dumps(PROBE.as_uri())};
globalThis.window = globalThis;
globalThis.document = {{hidden:false}};
globalThis.requestAnimationFrame = () => 1;
let callback;
globalThis.PerformanceObserver = class {{constructor(fn){{callback=fn;}} observe(){{}}}};
globalThis.CanvasRenderingContext2D = class {{constructor(){{this.canvas={{closest:()=>true}};}} clearRect(){{return 7;}}}};
installOverviewHistoryProbe();
for(let n=0;n<10000;n++){{
 const parsed=JSON.parse('{{"window_seconds":1800,"series":{{}},"rolling_5m":{{}}}}');
 if(parsed.window_seconds!==1800) throw new Error('JSON result changed');
 callback({{getEntries:()=>[{{duration:60}}]}});
 if(new CanvasRenderingContext2D().clearRect()!==7) throw new Error('canvas result changed');
}}
console.log(JSON.stringify(window.__overviewHistoryProbe.snapshot()));"""
    result = subprocess.run(
        [NODE, "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["historyParseCount"] == 10000
    assert data["plotClears"] == 10000
    assert data["longTasks"] == 10000
    assert len(result.stdout) < 2048
    assert not any(isinstance(value, list) for value in data.values())


def test_browser_phase_summary_does_not_infer_acceptance_from_short_runs():
    script = f"""import {{classifyPhase}} from {json.dumps(JOURNEY.as_uri())};
console.log(JSON.stringify(classifyPhase({{requested_seconds:3600, measured_seconds:3599, warmup_seconds:300, errors:0}})));"""
    result = subprocess.run(
        [NODE, "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "incomplete"


def test_journey_uses_real_pages_and_never_intercepts_healthy_history():
    source = JOURNEY.read_text()
    assert "page.route(" not in source
    assert "context.route(" not in source
    assert "newPage()" in source
    assert "collectGarbage" in source
    assert "post_gc_heap_bytes" in source
    assert "started_seconds" in source
    assert "completed_seconds" in source


def test_native_visibility_disables_playwright_focus_emulation():
    source = JOURNEY.read_text()
    assert "Emulation.setFocusEmulationEnabled" in source
    assert "enabled: false" in source


def test_only_history_outage_errors_are_expected_during_fault_controls():
    script = f"""import {{expectedOutageError}} from {json.dumps(JOURNEY.as_uri())};
const origin='http://127.0.0.1:15224';
console.log(JSON.stringify([
 expectedOutageError('Failed to load resource: status 503',origin+'/api/overview-history',true,origin),
 expectedOutageError('API Error: {{status: 503, message: Overview history is temporarily unavailable}}',origin+'/assets/index.js',true,origin),
 expectedOutageError('API Error: {{status: 503, message: Another API failed}}',origin+'/assets/index.js',true,origin),
 expectedOutageError('Failed to load resource: status 503',origin+'/api/overview-history',false,origin),
 expectedOutageError('API Error: {{status: 503, message: Overview history is temporarily unavailable}}','http://example.com/script.js',true,origin)
]));"""
    result = subprocess.run(
        [NODE, "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [True, True, False, False, False]


def test_navigation_logs_are_scoped_to_simulation_gps_and_cancellation():
    script = f"""import {{expectedNavigationError}} from {json.dumps(JOURNEY.as_uri())};
const origin='http://127.0.0.1:15224';
console.log(JSON.stringify([
 expectedNavigationError('Failed resource 503',origin+'/api/v2/gps/config',true,origin),
 expectedNavigationError('API Error: {{status: 503, message: GPS configuration not available in simulation mode}}',origin+'/assets/index.js',true,origin),
 expectedNavigationError('API Error: {{status: undefined, data: undefined, message: canceled}}',origin+'/assets/index.js',true,origin),
 expectedNavigationError('API Error: {{status: undefined, data: undefined, message: canceled}}',origin+'/assets/index.js',false,origin),
 expectedNavigationError('Other resource 503',origin+'/api/status',true,origin)
]));"""
    result = subprocess.run(
        [NODE, "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [True, True, True, False, False]


def test_sampling_records_a_final_gc_sample_after_deadline_despite_timer_jitter():
    script = f"""import {{measureResources}} from {json.dumps(JOURNEY.as_uri())};
let now=0;
const captured=[];
const last=await measureResources({{monotonic_seconds:0}},10,async gc=>{{const row={{monotonic_seconds:now,gc}}; captured.push(row); now+=0.001; return row;}},{{timerClock:()=>now,wait:async ms=>{{now+=ms>0?ms/1000-0.00045:0.001;}}}});
console.log(JSON.stringify({{last,captured}}));"""
    result = subprocess.run(
        [NODE, "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["last"]["monotonic_seconds"] >= 10
    assert data["last"]["gc"] is True
    assert any(
        row["monotonic_seconds"] < 10 and row["monotonic_seconds"] > 9.999
        for row in data["captured"]
    )
