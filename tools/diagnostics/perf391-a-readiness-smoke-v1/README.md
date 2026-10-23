# Original-A readiness smoke — stopped in preflight

Starting commit: `9b83eaf18c69102bbed06e166b51a4cb7b9dfbc2`.
Authority: [orchestrator checkpoint](https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6363126925).
**STOP for checkpoint review. Preflight failed; A executions: 0; C executions: 0.**

The bounded host preflight exited 1 before receipt validation completed. The
selected Python 3.11.16 interpreter used `PYTHONPATH=/usr/lib/python3/dist-packages`.
That system dependency selection was incompatible: importing jsonschema reached
referencing/rpds and raised `ModuleNotFoundError: No module named 'rpds.rpds'`.
This is an operator-side verifier environment failure, not an application,
frontend-readiness, Docker image or observer failure. No prerequisite repair or
preflight retry was attempted after failure. The historical ECONNREFUSED cause
remains unresolved. No functional smoke pass is claimed.

## Evidence and verification limits

[Preflight log](evidence/preflight.log) retains the full traceback;
[preflight result](evidence/preflight.json) retains the failure and actual command
results. The administrative preflight adaptation changes only task paths, starting
commit, checkpoint reference and the explicit approved readiness-overlay check.
The historical two-layer compiler/comparison and reviewed launcher/executor were
unchanged. The preflight wrapper can report historical source names in traceback
frames because it compiles the adapted text with that filename.

Confirmed in this session:

- Host is Forge; exact starting HEAD matches; approved frontend-readiness overlay
  SHA-256 is `ea21f78ca9f71d8b6b67222839727558cd586ebc3e2e438a4b935bd0482fcdec`.
  The active overlay checker returned before the dependency import failure.
- Initial read-only host inspection reached the actor rootless Docker 29.8.1
  daemon through inherited `DOCKER_HOST=unix:///run/user/1002/docker.sock`,
  context `default`. It reported 20 host threads and 65,915,523,072 bytes memory;
  these are host totals, not an enforced task budget.
- Initial host inspection found A ports 38080–38083 free, memory available
  55,360,638,976 bytes and `/tmp` free 24,508,928,000 bytes. No resource was started.
- Independent final host audit verified no task processes, port listeners,
  containers, networks or disposable volumes and removed the recorded scratch.

Incomplete or unavailable: full immutable receipt/image validation, historical
build-plan regeneration and approved logging comparison, source/patch/collector/
frozen release verification, exact Node/Playwright/Chromium verification and
CPU/cgroup preflight. No runtime launcher or executor invocation occurred.
Frontend HTTP readiness was never attempted; no backend, source observer, browser,
correlation ID, event timing, stream/final summary, loss accounting, retained-data/
projection/uPlot association or compositor screenshot evidence exists for this
session. No screenshot attempt or scheduled source/host observation occurred.
Missing runtime evidence is explicit and is not classified as zero evidence loss.

The existing 78-second work / 90-second outer / 10-second forced grace limits and
1.5-second source-observer gate remain unchanged and unexercised. The preflight
had a separate five-minute outer wall limit and ten-second forced grace; it
returned immediately with exit 1. See the retained invocation metadata.

## Cleanup and checkpoint

[Independent Forge host audit](evidence/final-host-cleanup.json) checks host PID
visibility, scoped A/C Docker labels and ports 38080–38083/38180–38183. It found no
survivors, no runtime root or lock, and removed only
`/tmp/perf391-a-readiness-smoke`, which contained its recorded ownership file.
The isolated worktree and evidence are preserved for review. No runtime resource
is left running. Existing images, shared configuration and historical failures
were untouched.

PRs #403/#405–#408 were verified open/draft/unmerged. #404 is an open issue,
not a PR. #390/#391 remain open. No image rebuild, packet capture, application or
Nginx change, calibration, benchmark, soak, merge, deployment or issue closure.
No retry and no C execution. Stop for checkpoint review.
