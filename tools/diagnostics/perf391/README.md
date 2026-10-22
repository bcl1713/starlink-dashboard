# Bounded source cadence diagnostics

This separate synthetic wrapper supports the first diagnostic phase of #391 in
PR #405. It is never an acceptance runner. It imports the frozen availability-v2
fixture/state adapter and existing process/Compose ownership helpers without
editing them. No production entrypoint imports these files. Both explicit
`PERF391_DIAGNOSTICS=1` and `PERF_SYNTHETIC=1` are required by the trace
backend; the runner sets them only in its isolated container.

Use the actor's configured Docker context/socket. Select the unchanged frozen
`f3029024` worktree and existing Playwright dependency root explicitly:

```bash
export PERF391_FROZEN_ROOT=/absolute/path/to/perf391-measurement-v2
export PERF391_BROWSER_ROOT=/absolute/path/to/checkout-with-installed-playwright
PYTHONDONTWRITEBYTECODE=1 timeout --kill-after=10s 15m python3 \
  tools/diagnostics/perf391/run.py \
  --sha e1f65798 \
  --project starlink-operator-diag391-your-unique-run \
  --output /absolute/path/to/new-evidence-directory \
  --instrumentation trace --viewers 2 --operator --warmup 5 --duration 30 \
  --total-timeout 800
```

The duration is capped at 120 seconds. Use `--instrumentation off` for a
separate control with the identical frozen state capture and diagnostic URL. Use
zero viewers and omit `--operator` for the unloaded workload. The matrix runner
runs two or three separate repetitions of both applications, workloads and
modes, alternating application order. Run the matrix under an external timeout
with at least 110 seconds termination grace so the owned child can finish scoped
cleanup. Do not run other performance jobs concurrently.

`PERF391_FAULTS=1` adds explicitly marked 700 ms controlled stalls. A 40-second
candidate control covers observer execution, worker dispatch/execution,
admission, collection, frame preparation, validation/publication, a real
repository lock holder, the backend loop and response sending. These runs must
remain separate from natural timing distributions. `PERF391_STOP_MODE=failure`
raises after browser setup; `timeout` deliberately waits for the owner's command
timeout. SIGINT/SIGTERM exercise cancellation cleanup. Preserve failures and
verify ownership records, process groups, listeners and Docker project resources
after every case. SIGKILL cannot run cleanup handlers.

Each run snapshots its diagnostic inputs and records source/image/package,
fixture, harness and diagnostic hashes. The exact application is archived and
built with the repository's production Dockerfiles; real Nginx and 1 Hz
Prometheus remain in the path. Loaded diagnostics require visible Overview and
Operator roots, recurring successful history/status traffic from both Overview
contexts, recurring Operator health traffic, and no browser errors. These checks
establish this short diagnostic workload, not full rendered acceptance.

The observer uses its own absolute 1 Hz monotonic schedule, a serialized source
read and the same one-second request deadline. This is a separate timing probe;
it does not modify, reimplement or certify the frozen acceptance validator.
`http.send` is the fetch invocation; `http.wire_send` is Undici's headers-send
notification; headers/body events distinguish response receipt and JSON parsing.
Buffering avoids per-request disk writes. Browser errors retain only type/path,
never response contents, query strings or error messages.

Backend spans retain monotonic nanoseconds and same-thread CPU, operation IDs,
thread IDs and hashed source/config/route/input/replay identities. No telemetry
values or mission payloads enter the trace. Repository holds include nested
admissions; only depth-zero holds should be aggregated. Span durations overlap
and must never be summed into total CPU savings. Async dispatch wall spans
include queued worker execution; their event-loop thread CPU is deliberately
excluded from worker CPU attribution.

A 50 ms heartbeat samples loop lateness in each process. Backend host samples
once per second include CPU pressure, host CPU counters, container `cpu.stat`
and per-thread scheduler runtime/wait counters where available. These samples
are observational, not proof of causality. Ancestor cgroup throttling and other
host processes may be outside visibility. Collection returns can contain
retained telemetry; completion cadence is not a physical acquisition census.

Join observer/backend records by `diag-N` request IDs. Subtract timestamps only
within their process/session. The HTTP residual is observer round-trip duration
minus backend ASGI duration; it combines transport/proxy/client work and cannot
be assigned to a one-way pre-ASGI network queue. A negative residual is retained
as uncertainty. Buffer overflow is explicit in `dropped`; never accept such a
trace as complete. Backend records are written on graceful shutdown after
workers are drained, and the owner verifies removal of all disposable runtime
resources.

Analyze a finished directory of runs:

```bash
python3 tools/diagnostics/perf391/analyze.py /absolute/path/to/runs \
  --output /absolute/path/to/summary.json
```

The output preserves timing distributions, request joins, failures and raw-file
hashes. Full raw traces and snapshots stay in the evidence directories. Never
interpret a short run without a recurrence as sustained acceptance or as a
causal explanation for the historical 1.755/1.584-second failures.
