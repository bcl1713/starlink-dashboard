# Diagnostic logging compatibility — stop for review

Starting commit: `ce86df20345feada04f1329d83d57fb657e71857`. Authority:
[orchestrator corrective checkpoint](https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6356322193).

The diagnostic-only `prepare.compose()` override now explicitly sets
`compress: "false"` for the `local` logging driver. Existing `max-size: "10m"`
and `max-file: "1"` limits remain unchanged for all three services in both
roles. No daemon configuration, image recipe, runner behavior, production
source, Nginx configuration or frozen benchmark tool changed.

Forge reports Docker **29.8.1**, source revision **464cd50**, default logging
driver `local`, and Compose **v5.5.1**. The exact revision's
[local driver](https://github.com/moby/moby/blob/464cd50/daemon/logger/local/local.go)
defaults compression to enabled and accepts the `compress` option. Its
[configuration validator](https://github.com/moby/moby/blob/464cd50/daemon/logger/local/config.go)
rejects compression with one file. Explicit false is supported and removes this
startup incompatibility while retaining the bounded limits.

## Validation and evidence

- `evidence/red.log`: the new Python regression first fails in all six service
  subcases with the original configuration.
- `evidence/offline-tests.log`: **22/22** offline preparation, closed-schema,
  identity and fixture-only executor tests pass in **6.392 seconds**. These
  tests use Python 3.14.4 and installed jsonschema 4.19.2; they start no real
  application, browser or Docker resource.
- `evidence/A.compose.json` and `C.compose.json`: actual
  `docker compose config --format json` results using immutable receipt image
  IDs. Both pass. C is rendered offline only; no C runtime run occurred.
- `evidence/validation.log`: a separately owned standalone Go harness compiles
  **unmodified** `upstream/config.go` from the actual daemon revision with its
  pinned `go-units v0.5.0` and `pkg/errors v0.9.1` dependencies. Defaults are
  extracted from that revision's retained `local.go`. Every rendered service
  passes Docker's actual `newConfig`; omitted/default compression, explicit true
  and invalid booleans fail deterministically. Six service subtests pass. Go
  1.26.1 compiles this pure configuration validator; the daemon itself uses Go
  1.26.8. No Docker logger instance or container was created or started.
- The retained-artifact audit passes both closed receipts, four image records,
  187 build-manifest entries and 621 Stage 5 release entries. The original
  failed A-smoke audit still passes all **37 artifacts**. Its report and
  evidence remain byte-identical; the failure is not reclassified as a
  successful smoke.
- `evidence/cleanup.json`: host inspection confirms all four accepted image
  IDs/labels/RepoDigests unchanged, no task processes/listeners, empty task and
  A/C project container/network/volume listings, and removed toolchain/cache and
  Compose scratch paths. No runtime resources were created. Open-PR worktree
  remains; primary checkout stays on `dev`.

The first Go harness assertion incorrectly treated `10m` as binary units;
`harness-unit-mismatch.log` is retained. Docker parses the unchanged value as
**10,000,000 bytes**. The assertion was corrected, with no configuration change.
An initial cleanup audit found the owned Go module cache's read-only
directories; `cleanup-readonly-cache.log` is retained. Only those owned
directories were made writable and removed before the final successful host
audit. These exploratory failures are not passing evidence.

## Revised identities

The original build plan, receipts, Stage 5 manifest, preparation checkpoint and
historical smoke/Node evidence manifests remain immutable. The active
`node-contract-overlay.json` corrected inventory now pins the changed
`prepare.py`; its original inventory remains unchanged. This supersedes the
previous active overlay hash without changing receipt-bound image labels.

| Identity                                     | SHA-256                                                            |
| -------------------------------------------- | ------------------------------------------------------------------ |
| Corrected overlay inventory (canonical JSON) | `19b1414453e101dc9bbbb93046c48ab553b22dfdcda4201eef5f5ac14427abae` |
| Active overlay manifest                      | `9e58db98dfaeb47fc617b6b0c7a98e6459ee8e1ad0e5c57fd69d1d665467cb02` |
| `prepare.py`                                 | `8d52a986514fefbec833b45f2a4b64b4e86a004983588116ec389ba3a467b001` |
| A Compose override (canonical JSON)          | `dab1035fd61762f6feb203c0a12210f362e0a7fbfaf8881e78e6ab3770b522f7` |
| C Compose override (canonical JSON)          | `96bdf2d8aed75b2180baaf60fea4e0a1b9fe7df5edf788e5da9b0e370bf0fcd5` |

`evidence/config-hashes.json` also records base and rendered configuration
hashes. `artifact-manifest.json` closes this checkpoint and pins the changed
external files plus unchanged receipts, build plan and failed-smoke manifest.

## Reproduction

Run the offline suite from the repository root:

```sh
PERF391_OFFLINE_ROOT=tools/diagnostics/perf391-built-images-v1/evidence \
  PYTHONDONTWRITEBYTECODE=1 timeout --kill-after=10s 120s python3 -B \
  -m unittest discover -s tools/diagnostics/perf391-runtime-preparation-v1 \
  -p 'test_*.py' -v
```

For the standalone Docker validator, supply a Go 1.26.1 toolchain and a private
module cache containing the two `go.mod`/`go.sum` dependencies. The checker uses
`GOPROXY=off` and `GOSUMDB=off`, verifies retained identities, renders both
Compose roles and runs only the local Go tests. Bound the entire command:

```sh
PYTHONDONTWRITEBYTECODE=1 timeout --kill-after=10s 120s python3 -B \
  tools/diagnostics/perf391-logging-compat-v1/check.py \
  --output /absolute/task-owned/evidence --go /absolute/path/to/go
```

Verify the retained checkpoint without Go, Docker or application startup:

```sh
python3 -B tools/diagnostics/perf391-logging-compat-v1/verify.py
```

**STOP for review.** No A retry, C run, application/browser launch, screenshot,
performance benchmark, calibration or sustained soak. A instrumentation remains
unqualified; C remains NO-GO. Preserve the **1.5-second observer cadence**. PRs
#403–#408 stay draft/unmerged (#404 is an open issue, not a PR), and issues
#390/#391 stay open. No merge, deployment or issue-state change is authorized.
