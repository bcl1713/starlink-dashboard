# Backend CI measurement and exhaustive shards

Issue 404 replaces the serial CI backend job with four isolated whole-file
shards and an always-running `Backend Test Gate` aggregate. The complete serial
`./tools/verify backend` and `all` paths remain available. Hosted acceptance and
two comparable normal PR rounds are pending; this document does not claim a
five-minute hosted result.

## Measured baseline and allocation

The immutable local M1 source was `2bf2fb12b8db85ab8599a452c0b693c67910d0a7`.
One complete serial run collected 4,295 cases in 346 files: 4,275 passed and 20
skipped. Pytest printed 634.48s; the observer measured 634.234s, including
1.114s collection and 631.274s summed setup/call/teardown phases. The separate
five family collections completed.

| Family           | Cases | Setup seconds | Call seconds | Teardown seconds |
| ---------------- | ----: | ------------: | -----------: | ---------------: |
| unit             |  2661 |         9.932 |      170.754 |            1.298 |
| integration      |   579 |         7.270 |       81.322 |            3.175 |
| operator         |   500 |         4.461 |       32.025 |            0.317 |
| planning         |   494 |        68.123 |      170.226 |            0.249 |
| itinerary import |    61 |        12.163 |       69.911 |            0.047 |

Planning dominates the family totals. Each file is assigned longest measured
phase sum first; normalized path then lowest shard number breaks ties. The
reviewable measured file costs, 346 explicit overrides, algorithm, source
identity, and skip reasons are in
[`backend_shards.json`](../../../tools/backend_shards.json). The four estimated
phase sums are 157.818, 157.818, 157.818, and 157.820 seconds. These exclude
each runner's independent setup, collection, and cleanup. New collected files
use SHA256(path) modulo four plus one and execute automatically. Stale overrides
are reported and do not manufacture test cases.

The historical hosted reference is normal PR 410 run
[40056822240](https://github.com/bcl1713/starlink-dashboard/actions/runs/40056822240):
827.65s pytest, 838.38s pytest command, 851s backend job, and 19.383 runner
minutes summed across backend/static/frontend. It used the same original backend
subtree, but different Python patch/uv/host and two setuptools 79.0.1 inventory
entries versus local 84.0.0/84.2.1. Local M1 used CPython 3.11.16, uv 0.12.19,
Linux x86_64, and 20 logical CPUs. The distributions and hardware are not
matched; comparing their elapsed times does not establish causal speedup. Two
optional process-counter point samples sum RSS to 736.9/871.5MiB; shared pages
may be counted twice, and these are not whole-run peak memory.

| Measurement              | Backend wall time | Total runner minutes     | Status                          |
| ------------------------ | ----------------- | ------------------------ | ------------------------------- |
| Hosted historical serial | 851s job          | 19.383, all three jobs   | Observed, unmatched environment |
| Local M1 serial          | 634.48s pytest    | Not a hosted measurement | Observed once                   |
| New normal PR round 1    | Pending           | Pending                  | Required                        |
| New normal PR round 2    | Pending           | Pending                  | Required                        |

Four runners trade wall time for repeated environment/collection work. Report
both backend critical path and summed runner minutes; five minutes is an
aspiration until normal CI supplies measured evidence. Do not use synthetic
fixtures or local phase sums as hosted acceptance results.

## Coverage and execution semantics

Every shard collects exactly `tests/` before standard pytest deselection. File
ownership comes from the collected `item.path`, preserving imported function,
class, and parametrized cases. Retained cases keep their original order. The
aggregate requires four successful jobs and exactly their current run/attempt
artifact directories. Reports must agree on full inventories and semantic
interpreter, distribution multiset, source, lock, runner, observer, verifier,
configuration, checkout SHA, and PR head identities. The merge checkout SHA is
bound to `github.sha`; PR head is recorded separately. Executable/temp paths,
CPU count, and kernel metadata are recorded but can vary across runners.

Selected inventories must be nonempty, disjoint, and exhaust the common full
collection. Each selected ID needs exactly one complete terminal result with
valid setup/call/teardown phases. Collection/session/internal errors,
interrupted or incomplete sessions, failed teardown, malformed or stale
evidence, altered assignment, or extra/missing reports fail the gate. Existing
20 skip identities and semantic reasons are explicit in configuration; new
skip/xfail allowances are not introduced. JSON duplicate keys, nonfinite
numbers, and booleans used as integer statuses/identities are rejected. Raw
phases, skipped reasons, slow-file Markdown summaries, command elapsed/status
logs, and ownership records remain downloadable for review.

The M1 full/family reconciliation originally found exactly two different IDs:
import-time `gzip.compress` headers included the current time. The
[explicit two-case ledger](evidence/case-renames.json) maps those original IDs
to `trailing-member` and `truncated`. Only those two rejection inputs now use
`mtime=0` and semantic parameter IDs; `b"not-gzip"`, the valid transport body,
test function body/assertions, and all nine module cases are unchanged. The
module passed once; two independent interpreter collections yielded identical
nine-ID manifests, retained in [gzip stable IDs](evidence/gzip-stable-ids.json).
No arbitrary node-ID normalization or loose equivalence is used. The archived M1
summary retains its historical blocked raw reconciliation finding; the ledger
explains its resolution. Final CI must retain all other original 4,293 IDs plus
these two explicit replacements and the five new offline controls.

The offline cartography fixture is function-scoped and opt-in. It supplies small
valid local Natural Earth geometries and denies downloads while retaining real
GeoAxes/projection, image, PPTX/ZIP, route/POI, and text rendering. Five added
controls cover distinct-route/repeatability/content, valid/unknown local
geometry, download denial, restoration, and real PPTX media/text. The existing
exporter case only adds fixture opt-in. Package/snapshot tests that omit PPTX
remain unchanged. No existing case/assertion, within-test concurrency overlap,
production tick, fixture lifetime, sleep, or backup test is removed or
shortened.

The accepted Stage 2 no-change findings remain: retain real slow planning,
long-history, WAL, filesystem, concurrency, and recovery behavior; do not widen
fixtures or accelerate production work for timing. Full-family assignment and
xdist on a shared runner were rejected in favor of measured isolated whole-file
jobs. Issues 391 and 408 are outside this change.

## Canonical commands and ownership

Use the [quality-gate commands](../../contributing/quality-gates.md) for serial
fallback. Each local shard needs its own full Git worktree/checkout and fresh
private root. Concurrent shards in one checkout are rejected by an atomic
`.backend-ci-active` claim; remove a stale claim only after verifying its
recorded PID/start identity, processes, and private root are gone.

For one already isolated checkout, supply an absolute evidence path outside the
private root. Run each of shards 1 through 4 in separate worktrees, with the
same checked-out commit and separate evidence directories:

```bash
ci404_sha=$(git rev-parse HEAD)
GITHUB_SHA="$ci404_sha" BACKEND_CI_PR_HEAD_SHA="$ci404_sha" \
  BACKEND_CI_RUN_ID=local-404 BACKEND_CI_RUN_ATTEMPT=1 \
 timeout --kill-after=10s 20m ./tools/verify backend --shard 1/4 \
  --report /tmp/ci404-artifacts/backend-report-local-404-1-1/backend-report-local-404-1-1.json \
  --run-root /tmp/ci404-local-1-private
```

Change the shard/root/artifact suffix for each independent checkout. Keep
`workflow`, Python, distribution multiset, uv, and source identities equal.
Reported unsharded execution also accepts
`--report ABS_JSON --run-root ABS_DIR`; plain `backend` and `all` still run all
cases serially without extra options. Unexpected inherited pytest override
variables are rejected before uv for reported/shard runs. No marker, keyword,
first-failure, retry, or auto-skip selection is added.

Create the explicit needs input and run the same stdlib aggregate validator:

```bash
python - <<'PY'
import json
from pathlib import Path
Path('/tmp/ci404-needs.json').write_text(json.dumps({
    f'backend_{i}': {'result': 'success'} for i in range(1, 5)
}))
PY
python tools/backend_ci.py check-needs --needs-json /tmp/ci404-needs.json
python tools/backend_ci.py gate --reports /tmp/ci404-artifacts \
  --needs-json /tmp/ci404-needs.json --sha "$ci404_sha" \
  --run-id local-404 --attempt 1 --pr-head-sha "$ci404_sha"
```

The Linux owner records command intentions, PID/start and process groups before
spawning, becomes a child subreaper, discovers detached descendants, and signals
only verified owned identities. PID discovery and cleanup do not depend on
optional socket diagnostics. FD denial is resampled for at most 100ms;
persistent same-identity denial fails. The reviewed owner class retains TERM 10s
then KILL/reap 2s defaults. The canonical report/CI boundary explicitly uses
TERM 5s then KILL/reap 2s to fit the outer 10s forced-kill grace, and reserves
cleanup inside the 20m budget. Each shard job has a 25m cap. Private bootstrap,
basetemp, and plotting/cache stores are removed after verified process/listener
cleanup; evidence is a separate retained sibling. Failed cleanup retains exact
ownership evidence and fails execution. Docker context, credentials, and shared
caches are preserved. No Compose resources or persistent server is needed.

## Dependency lock and reproducibility

Backend commands retain the original dev and GFS requirement inputs and add
`requirements-ci.txt`. Its 98 hashed runtime pins reproduce the original local
M1 inventory's 100-entry sorted multiset, including ambient pip and two visible
setuptools entries. The reviewed runtime setuptools pin is 84.2.1; ambient
build-tool 84.0.0 is preserved in the inventory rather than silently discarded.
[Lock comparison](evidence/lock-comparison.json) and
[preservation evidence](evidence/lock-preservation.json) record unchanged
versions and source hashes. This is source drift detection and pinned
resolution, not a claim that ambient build tooling has vanished.

CI pins tested uv 0.12.19 and uses setup-python's actual 3.11 executable with
Python downloads disabled. Cache identities include OS, architecture, actual
Python patch, uv version, all backend requirement files, and tracked Python.
Static and backend suffixes differ so a static dev-only cache cannot populate a
backend-union key. Each backend shard installs the same complete requirement
union. Static retains its pip development-dependency install.

For lock regeneration, copy the reviewed current lock before replacing it; this
published lock supplies constraints without an ephemeral file dependency:

```bash
ci404_constraints=$(mktemp /tmp/ci404-constraints.XXXXXX.txt)
cp backend/starlink-location/requirements-ci.txt "$ci404_constraints"
trap 'rm -f "$ci404_constraints"' EXIT INT TERM
timeout --kill-after=10s 5m uv pip compile --python 3.11 --generate-hashes \
  --constraints "$ci404_constraints" \
  backend/starlink-location/requirements-dev.txt \
  backend/starlink-location/requirements-gfs.txt \
  --output-file backend/starlink-location/requirements-ci.txt
```

Use uv 0.12.19 and the reviewed interpreter. Review any intentional dependency
change and reconcile the complete installed multiset before acceptance. Refresh
the fingerprint header after reviewing the regenerated pins:

```python
import json
import sys
from pathlib import Path
sys.path.insert(0, "tools")
from backend_ci import BACKEND_LOCK_HEADER, backend_lock_input_hashes
root = Path.cwd()
lock = root / "backend/starlink-location/requirements-ci.txt"
body = "\n".join(line for line in lock.read_text().splitlines()
                 if not line.startswith(BACKEND_LOCK_HEADER)) + "\n"
lock.write_text(BACKEND_LOCK_HEADER + json.dumps(
    backend_lock_input_hashes(root), sort_keys=True) + "\n" + body)
```

Source/requirements/configuration diffs remain reviewable. A stale source
fingerprint fails before backend dependency setup with regeneration guidance.
Never replace this procedure with unconstrained latest resolution.

## Durable evidence, acceptance, and rollback

The minimal baseline archive is committed here, independent of temporary task
paths:

- [M1 serial raw report](evidence/m1-serial.json.gz), including every phase.
- [Five family raw collection reports](evidence/m1-family-collections.json.gz).
- [M1 measured summary](evidence/m1-summary.json), including per-file timing.
- [M1 cleanup](evidence/m1-cleanup.json) and optional
  [resource point samples](evidence/resource-samples.jsonl).
- [Hosted serial summary](evidence/hosted-serial-summary.json) and
  [host distribution differences](evidence/host-distribution-differences.json).

Normal PR CI must supply all four independently isolated runs plus mandatory
static/frontend results, followed by a second comparable normal round. Compare
runtime hashes and backend Git tree identities across documentation-only heads;
do not rewrite earlier checkout/run facts. Inspect counts, the explicit two-case
ledger, skip reasons, timings, command status, runner minutes, and cleanup.
Current implementation verification is limited to bounded focused tools and
synthetic suites plus the nine-case gzip module. The mandatory static command
runs the source-controlled shard/gate/verifier/workflow/lifecycle contracts
alongside the existing policy and docs-link contracts.

Rollback restores the single serial `backend` workflow job with the same
`Backend Test Gate` name and
`timeout --kill-after=10s 20m ./tools/verify backend`. Keep required checks and
branch protection. Independently reviewed lock/offline fixtures may remain when
unrelated to a failure. Coverage loss, changed concurrency semantics, resource
leaks, dependency drift, reliability regression, or unexplained runner-minute
growth blocks acceptance. No issue completion or merge is implied by local
verification; normal PR gates, independent review, and the user's merge approval
remain required. Retain open-PR worktrees without task runtime resources.
