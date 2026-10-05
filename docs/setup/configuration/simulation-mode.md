# Simulation Mode Configuration

[Back to Configuration Guide](../README.md)

---

## Paced mission legs

On a Mission V2 leg, choose **Simulate leg…**, select a multiplier (0.1–1000) or
target runtime (at least 1 real second), then **Preview** and **Start
simulation**. A 20-minute planned flight at 10× takes about 120 real seconds.
The route needs valid timing; unsupported target rates and live mode are
rejected. **Activate** keeps its existing ordinary behavior.

Paced replay starts at adjusted planned departure immediately. Route movement,
communication events, flight elapsed time and planned POI countdowns share the
simulated clock. Planned speeds retain their flight units. Telemetry freshness,
history, ADS-B and acquisition timestamps continue to use real time.

Overview hides all five network cards and their header while a confirmed replay
is running, replacing them with run progress. Failed refreshes preserve that
layout and freeze the clock; ten seconds of silence also stops extrapolation.
Network cards return on completion/cancellation/failure/idle. The globe,
aircraft trail and follow preference remain available.

Completion preserves the active leg and freezes terminal flight values. The four
operational clocks return to real time. Deactivate to cancel; a new paced start
replaces the selected run. Backend restart clears active flags and returns idle.
Runtime targets can publish late under load; the result reports lateness. See
[paced simulation APIs](../../api/endpoints/simulation-run.md) for formulas,
validation and lifecycle details.

## Configuration Sections

### 1. [Simulation Mode Setup](simulation-mode/setup.md)

Overview of simulation capabilities, basic `.env` configuration, simulated
metrics (position, speed, network), and route configuration (circular vs. KML).

### 2. [Testing & Tuning Simulation](simulation-mode/testing.md)

Instructions for verifying simulation status, monitoring updates, and advanced
configuration via `config.yaml` (speed, variation, smoothing).

### 3. [Troubleshooting & Best Practices](simulation-mode/troubleshooting.md)

Solutions for common issues (stale position, missing metrics), and recommended
configurations for development, testing, and demonstrations.
