# Simulation Mode Configuration

[Back to Configuration Guide](../README.md)

---

## Ordinary Activate

For routine Operator evaluation choose **Activate** on a mission leg. This uses
the existing simulation sources and real elapsed time, without a paced replay.
Available synthetic network measurements appear as **SIMULATED DATA** and retain
normal freshness rules. Display presets and visibility settings still apply.
Deactivating a paced replay and using Activate restores these ordinary sources.

## Paced mission legs

On a Mission V2 leg, choose **Simulate leg…**, select a multiplier (0.1–1000) or
target runtime (at least 1 real second), then **Preview** and **Start
simulation**. A 20-minute planned flight at 10× takes about 120 real seconds.
The route needs valid timing; unsupported target rates and live mode are
rejected. Use ordinary **Activate** when you do not need accelerated flight
progression.

Paced replay starts at adjusted planned departure immediately. Route movement,
communication events, flight elapsed time and planned POI countdowns share the
simulated clock. Planned speeds retain their flight units. Telemetry freshness,
history, ADS-B and acquisition timestamps continue to use real time.

Overview preserves the configured visibility of all five network cards during
replay, including presets. Paced replay has no valid network performance model:
visible cards show Unavailable and suppress network readouts and history.
Route/PoP progression does not prove network performance. Ordinary activation
uses its existing synthetic model; live operation keeps the observed-data
display. Changing replay state or a failed refresh does not change display
preferences.

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

Instructions for verifying simulation status, monitoring updates, and
configuration via the actual `config.yaml` route, position, and network fields.

### 3. [Troubleshooting & Best Practices](simulation-mode/troubleshooting.md)

Solutions for common issues (stale position, missing metrics), and recommended
configurations for development, testing, and demonstrations.
