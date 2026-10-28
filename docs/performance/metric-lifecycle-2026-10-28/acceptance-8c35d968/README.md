# Paired-candidate acceptance review copies

The actual diagnostic soak candidate and performance harness are
8c35d968cfffd355fe609e7c96678b44fe979d73. The separate final acceptance
candidate is 4bbc93907294b8c40c9e751beb31f1ae901b0030. This evidence branch
remains based on the soak candidate, whose development base was
44d09d59f6eb60142e6f9ac0a0b676a6a019e353. Packaging did not change the tested
feature head or relabel the soak as the new final candidate. Authoritative
originals remain outside tracked content under the durable 2026-10-28
acceptance-review2 root.

[Runtime input equivalence](supporting/runtime-input-equivalence.json) records
the actual two SHAs and identical committed production backend/frontend,
Dockerfile, Compose, example-environment and performance fixture input
trees/blobs. The exporter independently recomputed every listed Git object.
This proves equality only for those committed inputs. It does not establish
image-bit identity, matching installed software versions or identical build
environments. Actual image identities and observed dependency/browser versions
remain separately recorded for each run.

These copies are not standalone platform authority. No discovery directory,
candidate-authority.json or fingerprint-authority.json is copied. Source
manifest members, checksum lists, seal receipt hashes and (when claimed by the
runner) the discovery binding were verified read-only before export. See
[manifest.json](manifest.json).

## Recorded outcomes

Final runner outcome: `passed`; `final_acceptance`: `true`; maximum evidence
claim: `final_acceptance`. Health outcome: `passed`; actual health source root:
`evidence/health-current-history/4bbc93907294b8c40c9e751beb31f1ae901b0030`.
These are the recorded source statuses, not new outcomes conferred by this
archive.

The formal final browser recorded degraded history with bootstrap HTTP status
[503] and the visible network-history fallback "History refresh unavailable".
`observedScheduledRequests` is `0`; the observation contains 0 scheduled
request rows. Live one-second polling and a five-second scheduled polling cycle
were not observed in this final capture. The degraded configuration period is
5000 ms; configuration and retained tests are separate from observed cadence.
The final pass covers this recorded degraded bootstrap/fallback branch; it does
not establish a successful live-history branch.

The first final attempt at `8c35d968cfffd355fe609e7c96678b44fe979d73` recorded
outcome `failed` and `final_acceptance`: `false`. Its journey incorrectly
expected the uploaded route name in the Globe legend, which displays Planned
route. The failed attempt is preserved as a historical non-final result. The
retention bug left that attempt without Compose/runtime observations; missing
artifacts are not represented as passed controls or recovered observations. The
new final candidate selects the corrected public journey and declares the full
static/build sequence again. Its recorded outcome and bounded logs determine
which checks actually completed.

The earlier final attempt at `44b86c5b878f8d9b051576bea7c6f21e60555668` under
the default host Node recorded `failed` with `final_acceptance: false` after a
frontend static test failed. That separate failed envelope is retained. The
task-owned Node 22.22.2 distribution meets the declared engine floor; system
Node 22.12.0 was preserved. The unchanged frontend subsequently passed its
standalone full suite with CI=1 under the task Node. The runtime and result
receipts preserve exact versions, command and counts. This does not prove that
Node version alone caused the earlier intermittent readiness failure. The
standalone result keeps its actual candidate SHA in its receipt. The current
generation repeats the full final lane in a separate evidence root.

The supported-Node formal attempt at `44b86c5b878f8d9b051576bea7c6f21e60555668`
also recorded `failed` with `final_acceptance: false`. Its static/build and
route/POI checks preceded a journey assertion for an obsolete history fallback.
Its separate failed envelope and cleanup proof remain visible. The
current-history final candidate is a later tooling revision; its separate full
final-lane result appears above.

The [replacement history
diagnostic](replacement-diagnostic/diagnostic-result.json) completed a frozen
draft journey against newly built production images from the actual
`44b86c5b878f8d9b051576bea7c6f21e60555668` code. It observed the current
history fallback, public route binding and distinct POIs. Its result explicitly
remains diagnostic-only with final_acceptance false; it is not the later formal
final lane. Provenance, actual image IDs, screenshots, 503 history responses
and cleanup receipts are retained. An earlier borrowed-image diagnostic was
blocked before runtime because those images were already absent; that result is
retained too.

Soak status: `failed`. Exact first-to-last measured span: `3619.9975862960005`
seconds; `sustained_60_minutes`: `true`. There are 725 measured resource rows.
The planned window was 3620 seconds. Raw duration and strict flag are preserved
without rounding a failure into a pass. Request failures, cancellations and
operation receipts remain in the raw source files.

The harness did not emit a native successful-run summary. [Derived
summary](soak/derived-summary.json) is a post-run descriptive calculation from
the unchanged report module, with source/module hashes and the original failed
status. The raw run records two Operator HTTP 409 responses on
`/api/v2/operator/record-changes` and `/api/v2/operator/records`, plus one
client cancellation. It is not a clean performance baseline. A true
strict-duration flag establishes only the recorded duration criterion; it does
not make the failed run pass.

The [Operator coordination investigation](soak/operator-409-investigation.json)
correlates the recorded queries, context receipts and later recovery. HTTP 409
response bodies were not captured. Any attribution of their cause is an
inference, not a recovered response body.

Final lane validation and the diagnostic soak shared the host. Concurrent
static checks, builds and browser work may affect CPU, latency and memory
measurements. There is no matched capacity or speedup comparison. The soak
browser mode and rendering backend are recorded separately from the final lane;
a headless software-rendered soak must not be promoted to final browser
authority.

Memory statistics are decimal MB, with fitted slopes in MB/min:

`backend.anonymous_bytes`: first 315.228, last 329.331, max 894.693; fitted
slope 0.452462.

`prometheus.anonymous_bytes`: first 36.262, last 48.652, max 52.150; fitted
slope 0.109472.

`browser.pss_bytes`: first 1179.277, last 1469.495, max 1534.855; fitted slope
3.685695.

Positive memory growth, transient peaks and retained TSDB history remain
visible; this record does not establish flat memory or a leak diagnosis. Full
precision and all resource/latency distributions are in [soak
summary](soak/derived-summary.json).

## Review files

- [Final runner manifest](platform-review/final/runner-manifest.json)
- [Final runtime observation](platform-review/final/runtime-observation.json)
- [Final browser observation](platform-review/final/adapter-observation.json)
- [Failed first final attempt](platform-review/failed-final-8c35d968/runner-manifest.json)
- [First final adapter failure log](platform-review/failed-final-8c35d968/adapter.stderr.log.txt)
- [Prior default-Node final failure](platform-review/failed-final-44b-default-node/runner-manifest.json)
- [Prior supported-Node formal failure](platform-review/failed-final-44b-supported-node/runner-manifest.json)
- [Health fingerprint review copy](platform-review/health/fingerprint.json)
- [Soak run and provenance](soak/run.json)
- [Soak summary (native or explicitly derived)](soak/derived-summary.json)
- [Soak lifecycle operations](soak/operations.jsonl)
- [Final cleanup receipt](supporting/final-cleanup.json)
- [CI job outcomes](supporting/ci-jobs.json)
- [Dependency drift diagnosis](supporting/dependency-drift.json)
- [Superseded runs](supporting/superseded-runs.json)
- [Superseded cleanup](supporting/superseded-cleanup.json)
- [Blocked health cleanup](supporting/health-blocked-cleanup.json)
- [Runtime input equivalence](supporting/runtime-input-equivalence.json)
- [First final runtime cleanup](supporting/failed-final-runtime-cleanup.json)
- [Independent soak cleanup](supporting/soak-runtime-cleanup.json)
- [Task Node runtime provenance](supporting/node-runtime-receipt.json)
- [Full supported-Node frontend result](supporting/frontend-supported-node-result.json)
- [Official Node checksum manifest](supporting/node-SHASUMS256.txt)
- [Parent review of final screenshots](supporting/screenshot-review-current-history.json)
- [Current candidate CI jobs](supporting/ci-jobs-current-history.json)
- [Current canonical static log](supporting/validation/static-current-history-restored.log.txt)
- [Current focused runner/browser 131-test log](supporting/validation/history-targeted.log.txt)
- [Retained acceptance-tooling log](supporting/validation/acceptance-tooling-current.log.txt)
- [Operator 409 investigation data](soak/operator-409-investigation.json)
- [Operator 409 investigation text review copy](soak/operator-409-investigation.md.txt)
- [Task ownership and supported runtime paths](supporting/task-ownership.json)
- [Supported-Node failed-attempt cleanup](supporting/failed-supported-final-runtime-cleanup.json)
- [Replacement diagnostic result](replacement-diagnostic/diagnostic-result.json)
- [Replacement diagnostic provenance](replacement-diagnostic/source-provenance.json)
- [Replacement diagnostic image identities](replacement-diagnostic/replacement-images.json)
- [Replacement diagnostic history responses](replacement-diagnostic/history-responses.json)
- [Replacement diagnostic cleanup](replacement-diagnostic/cleanup-verification.json)
- [Earlier blocked borrowed-image diagnostic](replacement-diagnostic/blocked-before-runtime.json)
- [Build ledger 2d35429da6a4](ledger/2d35429da6a42c444ce0da6184c6e1a8bd414e836ec8fcc51d40b65ecce5532f.json)
- [Build ledger 4636f95dd190](ledger/4636f95dd19078c661d639191395141e8cc57537e5831184d2609e72f4734de9.json)
- [Build ledger 4b0cd46028c1](ledger/4b0cd46028c11d7bfd80e1596a7225e21214e866489f455b4b912a9ab4e25583.json)
- [failed-final-44b-supported-node-neutral.png](screenshots/failed-final-44b-supported-node-neutral.png)
- [failed-final-8c35d968-neutral.png](screenshots/failed-final-8c35d968-neutral.png)
- [final-journey-post.png](screenshots/final-journey-post.png)
- [final-journey-pre.png](screenshots/final-journey-pre.png)
- [final-neutral.png](screenshots/final-neutral.png)
- [health-neutral.png](screenshots/health-neutral.png)
- [replacement-diagnostic-journey-post.png](screenshots/replacement-diagnostic-journey-post.png)
- [replacement-diagnostic-journey-pre.png](screenshots/replacement-diagnostic-journey-pre.png)
- [replacement-diagnostic-visible-page.png](screenshots/replacement-diagnostic-visible-page.png)

Superseded and blocked outcomes are retained as recorded; a later successful
result does not rewrite them. Cleanup receipts describe their recorded audit
times and owned resources. Packaging performs no new runtime cleanup audit and
starts no services. The final cleanup receipt reports status `clean`.

Build-ledger snapshots preserve actual image IDs and their recorded
usable/failed states for the soak, historical and current candidates. A usable
image ledger is not a passed product journey or proof that containers remain
running. The first failed final attempt's separate cleanup receipt includes the
disposable volumes removed by the owner.

## Archives, redactions and sealing limit

[platform-review.tar.gz](platform-review.tar.gz) contains only byte-exact,
privacy-screened platform members. Its original inventory files describe the
complete source evidence, including any members omitted from this review
archive. All members requiring host-path or debug-endpoint redaction are
excluded from that archive and provided separately as labeled review copies. No
sealed source file was altered. The manifest records original and published
hashes.

The archive cannot independently validate the platform seal: authority files
are deliberately absent, and privacy redactions can make the member set
incomplete. Only the preserved original root can serve platform readers. Public
checksum verification proves review-copy integrity, not platform publication
authority.

[soak-raw.tar.gz](soak-raw.tar.gz) contains resource rows, browser process/page
records and all separately captured cardinality rows. The investigation
Markdown keeps its original source name in the archive and uses a .md.txt
suffix for the readable review copy. Any privacy transformation is recorded per
source. Fixture names and operational receipts are synthetic. Credentials are
rejected, rather than copied. Screenshots still require human review before
publication. Large build inputs, container layers, source archives, unbounded
command logs and ownership dumps are not included.

`platform-review.tar.gz`: 379127 bytes; SHA-256
`9de431f0a2a72aa889c756174b72d28af5c68f6be98c30dc7beb6eafba073a2a`.

`soak-raw.tar.gz`: 807917 bytes; SHA-256
`36972f87be98616003ec3769cadd549c98133bb26f5c86c8db21b3d2f85492a5`.

Both archives use sorted USTAR members with zero UID/GID/mtime, mode 0644, then
gzip level 9 with an empty filename and zero mtime. This fixes metadata for
reproducible regeneration with the same Python/zlib implementation. Raw-member
checksum lists accompany each archive.

## Verify review-copy integrity

From this directory, verify direct files and inspect archive paths. The
archive-member checksums refer to published review bytes. Source seal
inventories refer to original bytes.

```sh
timeout --kill-after=10s 1m sha256sum --check SHA256SUMS
timeout --kill-after=10s 1m tar -tzf platform-review.tar.gz
timeout --kill-after=10s 1m tar -tzf soak-raw.tar.gz
```

To verify raw members without extracting files, run this bounded
standard-library check:

```sh
timeout --kill-after=10s 1m python3 - <<'PY'
import hashlib
import tarfile
from pathlib import Path
for archive in ('platform-review', 'soak-raw'):
    with tarfile.open(archive + '.tar.gz', 'r:gz') as bundle:
        expected = Path(archive + '-SHA256SUMS').read_text().splitlines()
        assert len(expected) == len(bundle.getmembers())
        for line in expected:
            digest, name = line.split('  ', 1)
            payload = bundle.extractfile(name).read()
            assert hashlib.sha256(payload).hexdigest() == digest, name
print('Review archive member checksums match')
PY
```
