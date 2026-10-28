# Review 3 acceptance addendum

Candidate: `46ed6af6d431cd7fac8633a9f3d829d5fc24d831`. Formal runner outcome:
`passed`; `final_acceptance`: `true`; maximum evidence claim:
`final_acceptance`. Health runner outcome: `passed`. Runner cleanup outcomes are
recorded in the original runner manifests; the later host audit is `clean`. CI
conclusion: `success` for exact `headSha`
`46ed6af6d431cd7fac8633a9f3d829d5fc24d831` (run `40763330778`). These statements
describe actual source receipts, not outcomes conferred by this archive.

The original watcher captured Xvfb but missed Chrome/profile ownership. A
separate post-run host audit verified absence from sealed runtime/log sources,
source-inferred Chrome process-group identity, current effective-UID process
scans, closed CDP/product listeners and the captured X socket. This supplements
cleanup verification; it does not reconstruct a historical Chrome/profile
capture. The host scan preserves explicitly recorded pre-existing shared
systemd/PAM services whose exact identities were approved after cwd access was
denied; it makes no cwd/exe absence claim for those shared services.

Observed final history mode: `degraded`. Bootstrap HTTP statuses: `[503]`.
Recorded scheduled requests: `0`; retained scheduled request rows: `0`;
configured period: `5000` ms. The selected adapter observation retains the
actual history/fallback, route binding, lifecycle and visible UI observations. A
configured polling interval alone is not an observed cadence. This addendum
makes no new one-second polling observation claim and establishes no new clean
performance baseline.

[Historical acceptance and failed soak](https://github.com/bcl1713/starlink-dashboard/blob/dce80fa9ba30d9574d418b4209ae46547f1ce198/docs/performance/metric-lifecycle-2026-10-28/acceptance-8c35d968/README.md)
remain immutable review history at `dce80fa9ba30d9574d418b4209ae46547f1ce198`.
The old diagnostic soak remains failed. Production Git inputs for this candidate
differ from the old soak; the previous 14-input equality receipt applies only to
its original candidate pair, including
`4bbc93907294b8c40c9e751beb31f1ae901b0030`, and is not transferred here.

## Validation evidence

- [Final runner result](final/runner-manifest.json)
- [Production image identities and public controls](final/runtime-observation.json)
- [Browser route, POI and history observations](final/adapter-observation.json)
- [Final screenshot](final/journey-post.png)
- [CI jobs](checks/ci.json)
- [Independent cleanup summary](checks/final-cleanup.json)
- [Source hashes and redactions](provenance.json)

The following summaries were extracted from the actual retained logs:

- `static-integrated.log`: `152 passed in 26.73s`
- `acceptance-tooling.log`: `451 passed in 120.24s (0:02:00)`
- `browser-contract-green.log`: `32 passed in 2.07s`
- `duplicate-red.log`: `1 failed, 31 deselected in 0.10s`
- `duplicate-green.log`: `1 failed, 31 passed in 1.46s`
- `final.log`:
  `=========== 4862 passed, 20 skipped, 5 warnings in 689.54s (0:11:29) ===========`;
  `Test Files  336 passed (336)`; `Tests  2337 passed (2337)`
- `health.log`: no pytest summary; inspect the retained log and source receipt

`duplicate-red.log` records the duplicate-row regression before the fix.
`duplicate-green.log` is an intermediate run with one dependency-related failure
and 31 passes; its filename does not confer a passing outcome. The later
`browser-contract-green.log` is the successful complete rerun after dependencies
were restored. The original logs and their separate results are preserved. The
static log also retains any nonblocking external-link availability warning.

## Provenance and archive limits

These are partial archival copies, not standalone platform authority. Original
platform manifests, checksum lists and seals were verified read-only with the
exact candidate's platform readers. No authority/discovery file is published.
`original-manifest.json` and `original-SHA256SUMS` in each group are byte-exact
source inventories: they intentionally list members omitted from this archive,
and do not verify the redacted or selected published subset. The top-level
`SHA256SUMS` verifies all published members except itself.

`provenance.json` records source/published hashes, byte counts, exact members
and narrow path redactions. Redaction rules publish symbolic IDs and hashes, not
the removed prefixes. `checks/final-cleanup.json` is a narrow summary with the
source receipt hash and aggregate verification/removal counts; full browser,
process and ownership identities remain only in the original outside-Git
receipt. The summary retains the parent-captured runtime generated-file
inventory's source hash and relative file names, sizes and hashes; original
UID/ctime proof remains outside Git. Those exact generated files were verified
again before the fresh runtime checkout was removed; this grants no general
permission to remove backend data elsewhere. Absolute task, checkout, actor-home
and pytest temporary prefixes are replaced only in published text copies.
Original evidence remains unchanged outside Git under the durable review3 state
root. PNGs and original inventories are copied byte-for-byte. Missing members of
failed captures are not reconstructed. This addendum does not duplicate the old
soak bundle.
