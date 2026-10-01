# Overview history fixture measurement report

Date: 2026-10-01. Issue: #224. Code commit:
`f42699e9c3e37f4bb9add51015ffd68bd6858bad` (clean working tree). Base: post-#216
`1542a7d6a64ade14fbef5f8b800e37266743b5c7`.

## Method and limits

These are computation/orchestration controls using deterministic dense finite
matrices through httpx MockTransport. They include fixture construction, JSON
decoding and backend projection/merging. They do not model internal Prometheus
five-minute range evaluation, a real HTTP server, browser parsing or graphics.
Raw and aggregate semantic correctness is covered separately by reference
comparisons, gaps, delayed zero observations, non-finite replacement, source
changes, failures and lifecycle tests.

Environment: Linux-6.18.44-x86_64-with-glibc2.41; Python 3.13.5. CPU exposed by
this shared workspace: INTEL(R) XEON(R) PLATINUM 8573C; 5 logical CPUs. Host
resource isolation, backend/Prometheus CPU and RSS, GPU, browser viewport and
browser heap were not measured. This is not the representative operator host.

Each case measures one cold load, then 120 polling intervals with two sequential
readers in each interval. Baseline uses the original full-window moving grid;
optimized cases use the documented fixed grid. Cold is excluded from warm
percentiles; demand-driven periodic full reconciliations remain included.
Five-second cases represent 600 simulated seconds; one-second cases
represent 120. Total query-work comparisons across cadences therefore need
normalization; these are per-operation controls, not equal-duration wall-clock
load tests.

## Query work and latency

| Window (s) | Reader / cadence | Cold (ms) | Warm p50 / p95 / p99 (ms) | Queries, two readers | Evaluation points | Median / max query span (s) |
| ---------- | ---------------- | --------: | ------------------------- | -------------------: | ----------------: | --------------------------- |
| 300        | full / 5s        |      18.9 | 16.0 / 25.7 / 28.2        |                3,840 |         1,878,240 | 300 / 300                   |
| 300        | incremental / 5s |      23.6 | 8.2 / 13.9 / 21.3         |                1,920 |            64,740 | 15 / 300                    |
| 300        | incremental / 1s |      18.2 | 8.9 / 16.8 / 36.0         |                1,920 |            37,440 | 11 / 11                     |
| 900        | full / 5s        |      36.2 | 36.8 / 52.6 / 62.8        |                3,840 |         5,622,240 | 900 / 900                   |
| 900        | incremental / 5s |      37.0 | 12.1 / 18.9 / 39.1        |                1,920 |            95,940 | 15 / 900                    |
| 900        | incremental / 1s |      39.1 | 11.7 / 18.2 / 22.6        |                1,920 |            37,440 | 11 / 11                     |
| 1800       | full / 5s        |      58.4 | 71.0 / 86.2 / 98.1        |                3,840 |        11,238,240 | 1800 / 1800                 |
| 1800       | incremental / 5s |      76.8 | 17.9 / 24.9 / 72.6        |                1,920 |           142,740 | 15 / 1800                   |
| 1800       | incremental / 1s |      87.3 | 17.5 / 26.3 / 32.5        |                1,920 |            37,440 | 11 / 11                     |
| 3600       | full / 5s        |      64.8 | 71.1 / 94.9 / 105.2       |                3,840 |        11,238,240 | 3600 / 3600                 |
| 3600       | incremental / 5s |      89.8 | 17.6 / 24.0 / 74.3        |                1,920 |           119,704 | 15 / 3600                   |
| 3600       | incremental / 1s |      73.9 | 0.0 / 19.7 / 24.2         |                  960 |            10,920 | 12 / 12                     |
| 3601       | full / 5s        |      44.9 | 50.5 / 69.9 / 71.4        |                3,840 |         7,494,240 | 3601 / 3601                 |
| 3601       | incremental / 5s |      52.4 | 13.6 / 18.3 / 53.1        |                1,920 |            82,888 | 18 / 3600                   |
| 3601       | incremental / 1s |      59.7 | 0.0 / 16.4 / 20.4         |                  640 |             6,240 | 15 / 15                     |

At 30 minutes, a healthy warm 1s advance queries 12 evaluation timestamps per
trace (312 total), compared with 1,801 per trace (46,826 total) for one full
read. The second reader adds zero upstream queries in every optimized case;
baseline adds 16. The five-second optimized comparison includes full
reconciliations and still reduces evaluation-point work substantially. Returned
sample counts are not measurements of Prometheus internal CPU or scan work.

## Full-bundle JSON cost

| 30-minute case   | Serialize p95 (ms) | Python parse p95 (ms) | Response bytes | Retained points |
| ---------------- | -----------------: | --------------------: | -------------: | --------------: |
| full / 5s        |               29.7 |                  21.5 |        931,015 |          46,826 |
| incremental / 5s |               30.8 |                  20.3 |        931,015 |          46,826 |
| incremental / 1s |               34.5 |                  22.5 |        931,015 |          46,826 |

The full public bundle still incurs serialization and client parsing cost on
each response. Reducing upstream computation has not eliminated those costs. The
dense fixture is larger than the reported operator screenshot; it is not a
network-bandwidth target or production payload measurement.

## Bounded state and local checks

- A separate 3,600-update / two-reader test runs one simulated hour in about 62
  seconds of wall time. It checks point caps, one cache configuration, no active
  refresh after each read, stable asyncio task counts and zero duplicate
  second-reader queries. It includes 12 full loads: cold plus reconciliation.
  This is not the requested minimum 60-minute wall-clock resource soak.
- 96 focused backend controls and 93 frontend history/provenance/projection
  controls pass. Full frontend ESLint, changed-file Black 26.5.1, filename and
  changed-line typing-policy controls pass.
- The chart timer/error processing-count regression is added but could not run
  locally because jsdom is absent. The full frontend build lacks
  three/drei/fiber; backend startup lacks reverse_geocoder. Existing threaded
  TestClient controls did not complete here; async ASGITransport API controls
  passed instead.
- Chromium launch fails with `setsockopt: Operation not permitted`; Docker
  daemon access is also denied by this sandbox. Production Docker/Nginx controls
  and a 1920x1080 recording remain pending. Ruff/canonical static checks and
  dependency-complete full suites require CI or a capable workspace.

## Acceptance and reproduction

The 1s default remains gated on the CPU/RSS/latency/browser budgets in the
[implementation plan](./2026-10-01-overview-history-efficiency.md). This report
does not establish #211 root cause or complete #224 acceptance. No recording
rules were introduced; authoritative trailing-five-minute PromQL remains in use.

From repository root, with backend httpx installed:

```bash
python tools/benchmark_overview_history.py --samples 120 --output /tmp/overview-history.json
```

For the state-bound control, from `backend/starlink-location`:

```bash
pytest --confcutdir=tests/unit tests/unit/test_overview_history_cache_bounds.py -q
```

Use the same representative host, hardware, viewport, windows and real telemetry
for baseline 5s, optimized 5s and optimized 1s production acceptance. Record
CPU/RSS, browser heap/long tasks/upload frequency, p50/p95/p99 and the exact
SHA. Enable the default only after the real >=60-minute soak and motion
recording pass. Rollback is a frontend rebuild with
`VITE_OVERVIEW_HISTORY_POLL_SECONDS=5`.
