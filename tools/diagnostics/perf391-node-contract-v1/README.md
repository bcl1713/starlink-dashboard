# Diagnostic Node contract correction — STOP for review

Starting source: `8db5a3567dbc62bf65889976cb2ff566a0a964c1`.
Authority: [latest orchestrator review](https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6355528452).
The delivery commit anchors the exact source and this evidence inventory.

The diagnostic browser owner requires **Node 22.22.2**, SHA-256
`81925c0995b5c1427b5d538e6a90ca2fdc4daffb786b09af749beaf7369d4e90`.
This is receipt-bound diagnostic functionality qualification. Image build and
app-side Node minimum remains 22.22.2. Historical frozen benchmark Node remains
**22.12.0**, SHA-256
`177208bfc4a9403121a40c72d038c670f4fd937fa16ca7df0a720e90be0fe2d9`.
No frozen comparator, application source or matching rule changed; diagnostic
smoke timings must not be compared with historical controls.

## Verification

**21/21 tests pass in 5.906 seconds** under Python 3.11.16; see
[evidence/tests.log](evidence/tests.log). The complete runtime-preparation suite
covers both receipt roles, wrong version/hash pairs, actual executable hash and
version rejection, original/corrected overlay integrity, assets, missing images,
invalid receipts, failed startup commands, process-spawn errors, actual SIGTERM,
cleanup failure reporting, scoped teardown and reaping of every owned child.
The actual proposed executor and real process Owner run; every external command
is replaced with a Python fixture. No Docker/application/browser process runs.
Port binding and exclusive-subreaper setup are simulated in this executor test;
actual container topology and escaped-descendant adoption remain outside this
qualification. No runtime capability or performance acceptance is claimed.

Reproduce from repository root with a Python 3.11 environment containing
`jsonschema==4.19.2`:

```sh
PERF391_OFFLINE_ROOT=tools/diagnostics/perf391-built-images-v1/evidence \
  timeout --kill-after=10s 90s /reviewed/python3.11 -B -m unittest discover \
  -s tools/diagnostics/perf391-runtime-preparation-v1 -p 'test_*.py' -v
```

The private executable was extracted **without creating any container**, by
saving the retained pinned Node image and reading only `usr/local/bin/node`
from its layers. Its hash and `--version` match the receipts. Both Playwright
packages are 1.63.0 and declare Node `>=20`; the receipt-bound Node imports the
API and resolves the exact configured Chromium revision **1243** executable,
SHA-256 `8c599d43aec53f2460a31ae2f4af6bd863f8258b34ff519564bc5d4726bfaa1e`.
[evidence/runtime-identity.json](evidence/runtime-identity.json) retains package,
metadata and binary hashes. No Chromium command or browser launch was issued.
Actual browser startup compatibility remains unqualified.

Black checks pass for the six changed runtime/test Python files. Full configured
Ruff passes for the three new runtime/test files. Broad Ruff on existing files
still reports inherited style findings (including long lines); it is not claimed
as passing. Git whitespace checks pass. The retained-artifact audit checks the
187-file build inventory, assets/dependencies/image records and 621-file Stage 5
release, replacing only the superseded overlay check with the explicit original
plus corrected inventory check.

## Immutable receipts and revised proposal

- Build plan SHA-256: `8537bddee63b76d65f08548d447fbc93f42dfbe919b09f4fc9826d4e128954d5`.
- A receipt: `7d337809082015880bb51e69bcf8973fd5036518286b876dda77145543c9c24f`.
- C receipt: `a9b7492aed2e90448d2ed8aeb4586dccd667d03e1cbb0829ff759a04537109e2`.

All four accepted images, receipts and historical evidence remain byte-for-byte
unchanged. [evidence/immutable-identities.json](evidence/immutable-identities.json)
records every image ID; cleanup also freshly verifies daemon IDs and labels.
The separately hashed `node-contract-overlay.json` authorizes the corrected
launcher/executor/schema/helper over the original build-plan inventory, without
rewriting the receipt binding. Earlier manifests describe their historical
source revisions; the new artifact inventory describes this correction.

[evidence/launch-A.proposed.json](evidence/launch-A.proposed.json) is an offline
proposal, **not authorization**. Recreate and verify a private exact Node copy
before a separately authorized A-only smoke; supply that path to `--node`.
Regenerate the launch JSON from the unchanged retained plan/receipt, require fresh
image/context/port/headroom/ownership checks, retain five samples at 1 Hz,
78-second work / 90-second outer / 10-second force grace, one chart join and at
most one screenshot attempt. The 1.5-second cadence requirement is unchanged.
Do not run this proposal until reviewed. No A, C, calibration or sustained run.

## Execution notes and cleanup

The new receipt regression first failed in eight subcases, including acceptance
of wrong hashes and later Node versions; it passes after the correction. Initial
fixture setup/import/assertion mistakes were corrected. Sandbox asyncio thread
wakeups stalled both ambient Python 3.14 and Python 3.11; a minimal host probe
passed, and final tests ran on the host. Bounded stalled runs ended by timeout;
old processes were verified gone before replacement. One minimal stalled probe
was explicitly terminated by its verified PID. One suite invocation used the
wrong root-relative plan path and failed setup; the final full run above passed.
A sandbox formatter timeout completed before host formatting. These exploratory
failures are not passing evidence.

[evidence/cleanup.json](evidence/cleanup.json) records no host process survivors,
empty A/C scoped Docker resources, empty ports 38080–38083/38180–38183, and removed
private Node/export/environment and timeout fixture paths. Successful tests
assert each owned child was reaped and absent from `/proc`. No real container,
network, volume, listener or browser was created. Retained images, shared actor
Docker configuration and credentials are preserved. The open-PR worktree remains.

STOP for review. #403–#408 stay draft/unmerged; #390/#391 stay open. No services,
application HTTP, image builds, capture, calibration, sustained tests, merge or
deployment. Raw-wire provenance remains unavailable.
