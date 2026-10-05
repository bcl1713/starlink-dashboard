# Paced mission simulation

[API endpoints](README.md) ·
[Simulation configuration](../../setup/configuration/simulation-mode.md)

Paced replay is available only in simulation mode. It uses the selected leg's
effective timed route, including adjusted departure and a feasible Manual AR
splice. Preview is read-only; starting revalidates the plan before changing
active state.

## Preview and start

`POST /api/v2/missions/{mission_id}/legs/{leg_id}/simulation/preview` accepts
exactly one pacing mode:

```json
{ "mode": "multiplier", "multiplier": 10 }
```

```json
{ "mode": "target_runtime", "runtime_seconds": 120 }
```

Multiplier limits are inclusive **0.1–1000**. A target runtime must be at least
**1 real second**, and its derived multiplier must be within those limits.
Numbers must be finite JSON numbers; unknown fields are rejected.

Every normalized route segment needs positive duration. Duplicate untimed
vertices need removal or distinct timing anchors. A missing or unavailable
selected diversion rejects paced preview rather than replaying the base route.

For planned duration `D` simulated seconds, multiplier `M` gives `D / M` real
seconds. Target runtime `R` gives multiplier `D / R`. A 1200-second flight at
10× and a 120-second target therefore produce the same pacing.

The response includes `pacing`, `effective_multiplier`,
`flight_duration_seconds`, `expected_runtime_seconds`, `planned_departure`,
`planned_arrival`, `limits`, and a 64-character `plan_token`. Send the exact
pacing and token to the existing activation endpoint:

```json
{
  "simulation": {
    "pacing": { "mode": "target_runtime", "runtime_seconds": 120 },
    "plan_token": "<64-character token returned by preview>"
  }
}
```

`POST .../activate` returns the existing `status` and `active_leg_id`, plus
`simulation_run`. A bodyless activation or `{}` retains ordinary activation
behavior. Explicit 1× starts immediately at planned departure, even when the
planned date is historical or future.

## Shared status and geometry

`GET /api/simulation/run` returns:

- `runtime_id`: backend incarnation identity; changes on restart.
- `revision`: increases on accepted frames/lifecycle changes, never on GET.
- `service_mode`: `simulation` or `live`.
- `state`: `idle`, `running`, `completed`, `cancelled`, or `failed`.
- `served_at`: real UTC response time.
- `run`: null while idle; otherwise the last confirmed run snapshot.

The snapshot contains run/mission/leg/route IDs, normalized pacing and token,
planned departure/arrival, simulated time, real start/observation/finish times,
elapsed real seconds, route distance progress, phase, processed event count,
transport states, optional error, and completion lateness. Distance progress can
differ from elapsed-time progress on routes with varying segment speeds.

`GET /api/simulation/run/{run_id}/route` returns `{runtime_id, run_id, route}`
using the existing route-detail shape. It supplies the effective geometry for
the selected running/completed replay; normal route APIs continue to expose
stored plans. Superseded or unavailable geometry is 404. Status, preview, and
geometry responses use `Cache-Control: no-store`.

Flight status and Overview upcoming-POI responses add optional `mission_time`
with runtime/run IDs, revision, simulated time, observation time, phase and
multiplier. Response/acquisition timestamps remain real UTC. Planned segment
speeds are measured per simulated second and are never multiplied by pacing.

## Lifecycle and errors

All due canonical events are processed once in stable order, including events
crossed between collection frames. Arrival clamps to the exact endpoint, 100%
progress and POST_ARRIVAL without automatic live departure/arrival dwell delays.
The active leg remains available for review. Completed flight elapsed values
stay frozen; the four Overview timezone clocks return to real time.

Deactivation, direct route changes, accepted configuration changes and shutdown
cancel a running replay. Ordinary activation clears the selection; another paced
start replaces it. Running plan edits and manual flight changes return 409.
Existing active-leg deletion protection still requires deactivation first. Only
one run is retained; restart returns idle with a new incarnation and cleared
active-leg flags, without resuming a run.

| Status | Meaning                                                                                    |
| ------ | ------------------------------------------------------------------------------------------ |
| 404    | Missing mission, leg or selected run geometry                                              |
| 409    | Live mode, changed preview plan, incompatible running edit                                 |
| 422    | Invalid pacing, unsupported derived rate, missing/inconsistent timing or unusable geometry |
| 503    | Runtime not ready                                                                          |

After a changed-plan conflict, preview again. A failed start compensates its
activation side effects and retains the prior confirmed runtime. Failed frame
publication does not advance the event cursor or renew observation freshness.

Scheduling uses monotonic elapsed time. Publication can be late under CPU/I/O
load; `completion_lateness_seconds` reports that delay. A target runtime is a
deadline target, not a hard real-time guarantee.
