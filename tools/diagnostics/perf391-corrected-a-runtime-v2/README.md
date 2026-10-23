# Corrected original-A runtime preparation

Offline preparation passes. **STOP for review; A/C runtime remains unauthorized.**
Authority: [latest orchestrator checkpoint](https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6372344239).
Starting commit: `07c68cda45d541ea2817f750bd56ca3da9de9702`.

This additive package selects the qualified corrected A images and approved
corrected scripts. Every pre-existing tracked file remains unchanged. Historical
plans, closed receipts, asset comparators and all eight historical/corrected
images remain separate immutable inputs. No application, asset, image or receipt
was edited. No image was built, pulled or pushed.

## Active identities

| Artifact | Exact SHA-256 |
| --- | --- |
| [A launch](evidence/launch-A.json) | `f15d657727bd029e54233e783cfa1acdf18f6889c7180f9dba4158c4182ce0e2` |
| [Effective Compose](evidence/A.compose.json) | `4dd55d0becb437f58942e5b3e5d117480ce0258bf953d6610b6e3024d449179d` |
| [Compose base](evidence/A.compose.base.json) | `591e4e381bb572b8284ee79a0cf0012a083aede83f4727dceca2662c5781a939` |
| [Compose override](evidence/A.compose.override.json) | `5419094df7e1bb5dbae1f0282aa0e4881d5a5f73e1b9c09fd83746d3fc36764c` |
| [Runtime identity overlay](identity-overlay.json) | `78e44168dceeeaad82bbcd2ced9a0d92aabcae554ebb02cf775b431904f7c6c9` |
| Corrected build plan, preserved | `7b96a51d675b9b9c26787dfa06c2fe8458816b0088b2568e6707d6b5a7de7ca7` |
| Historical build plan, preserved | `8537bddee63b76d65f08548d447fbc93f42dfbe919b09f4fc9826d4e128954d5` |
| A v2 lineage receipt | `785b24fc61fdd196ac64e9dd2ae1afd39b7210c73acbc711b614f39ab8235725` |
| A compatible-v1 receipt | `eba5c87d4e619a5468e96b6829d52c4ed0d24bff115ce043551cc6399a0281d4` |
| A historical receipt | `7d337809082015880bb51e69bcf8973fd5036518286b876dda77145543c9c24f` |

The lineage receipt links correction source
`31b1fbbfded503344e9df653ba148850a2e69f95`, delivery
`e40b9ff240ce97af0c03ac254b52a8af084634bd`, and correction overlay
`43a28519858ed545e5fe2ed8720a1437985b40e4dd49f8d3675b5ea5f954a970`
to both plans, both receipts and these actual daemon identities:

| Image | Historical ID | Selected corrected ID |
| --- | --- | --- |
| A backend | `sha256:8b8518fe1007170ce423b76f98958d85a4153927a0d8e59930d3790f38318abd` | `sha256:87a2379218610bd64b4e9e332a0d1bd70ed3fabe673c0dee8c865950d5fc9747` |
| A frontend | `sha256:aee6d4fdf4a1c7746c8e4ba65458aa3160ffb8d1792982ba56a3e1cb1745dd88` | `sha256:f3d62a630ea1c8be51a609b611a50d1e3725a7f2f8d83d530dea6ff78f3b9df5` |

## Runtime selection

[binding.py](binding.py) reuses the historical scheduling compiler without
passing a v2 plan to a v1 schema or changing the receipt's plan hash. It separately
validates the exact corrected plan and closed compatible receipt, replaces the
two image selections and explicit context/browser paths, then adds the versioned
identity binding. C is rejected by this adapter. All deadlines, ownership,
resource limits, loopback ports, logging and network settings are inherited.

`bound_executor()` imports the existing corrected executor without executing its
coroutine. Its five preflight hooks select the new strict binding validator,
receipt validator and A-only compiler. These verify actual hashes and schemas;
none is a no-op. The historical executor and its historical rejection guard remain
unchanged. The adapter's command line rejects `--execute` before doing any work.
This checkpoint supplies no runtime command or authorization.

The launch and overlay inventory pin the actual selected source paths and hashes:

- `perf391-runtime-preparation-v1/browser-owner.proposed.mjs` imports corrected
  `perf391-diagnostic-integration-v1/collect.mjs`, which imports corrected
  `browser.mjs`. The owner imports corrected `browser-evidence.mjs` for Finish.
- The image's compiled frontend probe comes from corrected `browser-probe.ts`
  through unchanged `browser-runtime.ts`; the 29 served files and emitted live
  module closure match the receipt and stopped-image extraction exactly.
- The bound executor imports `frontend_readiness.py` and `backend_evidence.py`;
  callable source locations are checked. Its existing `finally` path preserves
  backend exports after browser/frontend failure before Compose teardown.
- Corrected `analyze-runtime.py` retains the five-wake, maximum 1.5-second gap
  check. `observer.mjs` retains its absolute 1 Hz schedule and skipped-deadline
  accounting. The runtime still requires **78 seconds work / 90 seconds total /
  10 seconds forced-termination grace**.

No script from the temporary historical compiler export enters the active launch.
That export is solely the immutable source/context comparator. The complete
non-evidence source closures are inventoried by the new overlay. The launch
retains the reviewed installation's original absolute receipt paths; it is a
local Forge artifact, not a portable manifest.

## Verification and limits

[preflight.py](preflight.py), [verification](evidence/verification.json) and
[command ledger](evidence/commands.json) record the bounded offline checks:

- Existing corrected retained-artifact validator passes, including closed v2 and
  compatible-v1 schemas, historical receipt lineage, dependencies, served assets
  and compiled module closure. The read-only final verifier also validates both
  historical closed receipts against their original plan.
- The original guarded compiler regenerates its complete plan byte for byte.
  Applying only the three approved diagnostic replacements and retained recipes
  reproduces the corrected A/C context inventories and corrected plan exactly.
  No C launch is generated. A application SHA-256 is
  `015c5f515438b7114f903e90c5c43014a2b29fb6c316fdbca0232681585c5baa`;
  corrected A context is
  `215801d9cedaf8a055a876d1fb6d78745462ceebad91de291eb9fd33b8a287d7`.
- Fresh actor-daemon inspection matches all eight image IDs, tags, RepoDigests,
  full configs and rootfs layers. Only corrected A was extracted, using two
  never-started containers. Backend diagnostic/app/test/frozen-fixture/renderer
  files, dpkg/apk inventories and all 89 Python package identities match.
- All 29 frontend files, the actual served index and compiled module closure
  match. Asset-map SHA-256 is
  `9637a1b8a5a269e8a61090bbc1982a5f5578409536574fa45b66abce146ab80e`;
  module-closure SHA-256 is
  `cc01ff100b633b664ee4a309e73181eda52069e834f67529d46f824bdf232322`.
- Actual extracted Node 22.22.2 is hashed and runs only `--version` and syntax
  checks. The existing browser identity validator imports Playwright 1.63.0's
  API without launching, checks Chromium revision 1243 and executable hash, and
  hashes the full installed browser distribution. Chromium is never executed.
- One final A launch and effective Compose rendering pass. Whole-config equality
  against the approved prior non-internal config allows only corrected A image
  IDs, context paths and explicit project namespace. This preserves `json-file`
  logging, `compress: "false"`, `internal: false`, CPU/memory/PID limits, loopback
  publication, and the HTTP index-readiness gate.

No new regression suite or redundant identity tests were added. No fixture suite
was rerun; prior build qualification results remain attributed to that checkpoint.
Syntax/import/source/config checks establish selection, not live browser drain,
paint, loss or backend shutdown correctness. Prior build caveats remain visible
in the unchanged corrected-image report. Original A remains FAIL; C is NO-GO.

The [initial attempt](evidence/initial-attempt/verification.json) reached all
image/source/dependency/Compose checks, then stopped on this package's mistaken
search for the cadence literal in the observer. The limit lives in the analyzer;
only the check was corrected. Its independent cleanup passed before the final
preflight. Both attempts' actual command records remain retained.

## Cleanup and review gate

The final independent [host audit](evidence/cleanup.json) verifies 33 recorded
PID/start identities, no task process survivors/listeners, empty scoped Docker
containers/networks/volumes and the removed temporary root. Both extraction
containers stayed `created`, PID 0, zero start time, and were removed. Temporary
source/context/dependency exports were removed. All eight images and immutable
evidence remain. The primary checkout stays clean on `dev`; the task worktree
remains for review. No runtime resources are retained.

The launch records `/tmp/perf391-corrected-a-preflight/contexts/A` as its exact
validated context provenance. That temporary tree is deliberately absent after
cleanup. A separately authorized future runtime must regenerate and revalidate
that same context before use; the unchanged executor also rehashes it. Do not run
`preflight.py` concurrently with a future runtime, since its task-owned context is
removed on exit. Revalidation of retained evidence alone is read-only:

```sh
timeout --kill-after=10s 3m python3 -B tools/diagnostics/perf391-corrected-a-runtime-v2/verify.py
```

No services, browsers, A/C runtime, packet capture, calibration, benchmark,
sustained test, merge, deployment or issue closure occurred. PRs
#403/#405/#406/#407/#408 remain draft/open/unmerged; #404 is an open issue.
#390/#391 remain open. **Stop for orchestrator review.**
