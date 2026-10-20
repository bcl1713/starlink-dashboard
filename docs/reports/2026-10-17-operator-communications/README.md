# Operator communications verification

Issue 365 in epic 361 adds requirements and retrospective call corrections to
Operator. The exact tested product is
`de9567cec70aff570ff99f176a02e46e91ad4559`; later report/documentation commits
do not change product code. PR 375 targets `dev` and remains draft for product
review.

## Delivered behavior

The responsive Communications section supports voice/VTC/other or unknown type,
UTC requirements, signed minute/hour shifts, unknown duration, preparation lead,
status changes, retrospective actual start/end, and optional party/coordinator,
conference reference and notes. Call history, association corrections,
remove/restore, receipt replay and version conflicts reuse the existing journal.
Call changes never close a conference.

New planned requirements default to ten minutes of preparation. Explicit null,
zero and legacy missing values remain distinct from creation-time omission; full
call replacements require an explicit nullable lead. Corrections to old
scheduled records can preserve unknown planned timing. Planned, actual and
recorded timestamps remain independent. Preparation cues derive from the latest
saved values and backend snapshot clock; live alerts remain issue 368.

Independent review identified historical receipt fallback, numeric draft loss
across store replacement, stale Saved cues and misleading overdue status copy.
Regression tests reproduced these before correction. Acknowledged saves now
require current-row reread before reopening/discarding; recovery preserves raw
numeric drafts, dirty edits hide Saved, and summaries show actual call status.
The report does not claim a separate external product approval.

## Verification

[Verification results](verification.json) records final test outcomes and
versions. The initial complete backend run passed 3,968 tests with 20 skips; the
final run includes the added legacy scheduled-time correction regression. The
final exact frontend suite passed 1,771 tests across 248 files and its
production build.

[Production acceptance](acceptance.json) records exact image identities,
archived source checksum, Nginx traversal, qualified checks and cleanup. The
private project was `starlink-operator-365-final`; raw synthetic evidence
remains at `/tmp/operator-365-final`. Both actual Docker images carry the full
product SHA. The rootless internal network used the existing owned Docker-exec
byte relay to reach production Nginx; application source and browser bundle came
from images.

All four production browser journeys passed:

- Communications: desktop 1920×1080, portrait 390×844 and landscape 844×390; UTC
  midnight shifts without invented duration; cancel/reinstate; 1600Z entry of an
  unscheduled 1430–1442Z call, correction to 1445Z and a new party; between-leg
  association, immutable history, remove/restore and unchanged shared
  conference.
- Two browser clients: stale edits conflict, local drafts remain, explicit
  reread gets the current correction; offline retry repeats the exact
  body/key/epoch, withheld acknowledgment does not show Saved, and SQLite has
  one receipt/revision.
- Existing display controls, passive Overview visibility/history and journal
  workflows, including real read-only-media 503 and recovery, remain covered.
- Existing shell ordering, three mission scopes, mobile navigation,
  failure/reconnect and restart retain their production checks.

[Communications proof](communications-proof.json) contains the per-scenario
flags. [Storage failures](failures.json) includes crash/WAL, media,
backup/recovery and store-epoch probes. [Export compatibility](exports.json)
checks existing mission and per-leg telemetry artifacts; the communications
projection probe inspected all three corrected retrospective records after
browser restart. Optional provider access was deliberately unreachable and
browsers blocked external feeds.

## Sanitized artifacts

| Artifact                                          | Purpose                                            |
| ------------------------------------------------- | -------------------------------------------------- |
| [Desktop](communications-1920x1080.png)           | Actual 1920×1080 production view                   |
| [Portrait](communications-390x844.png)            | Actual 390×844 production view                     |
| [Landscape](communications-844x390.png)           | Actual 844×390 production view                     |
| [Current record](operations-current-example.json) | Corrected synthetic call                           |
| [Audit](operations-audit-example.jsonl)           | Original and corrected/removal/restore revisions   |
| [Activity](operations-activity-example.jsonl)     | Before/after timing, party and association changes |
| [Example metadata](examples.json)                 | Selected record and source/example checksums       |

Examples are filtered excerpts of the actual production journal projections, not
a new mission ZIP/export implementation. Mission-package wiring remains
issue 370. Inputs, parties, coordinates and captured records are synthetic.
Software simulation does not establish aircraft readiness.

## Compatibility and backout

There is no new SQLite table or schema migration. Old accepted payloads and
receipts are not rewritten. Back up the intended namespace before upgrade.
Disable Operator to hide its workflows while retaining the database and shared
configuration. Older binaries with closed payload models cannot read the new
call fields: stop access, preserve the newer store, and restore an explicitly
selected pre-upgrade backup before downgrading. Restore rotates the epoch and
can lose entries newer than that backup. Do not initialize a replacement store
or delete retained volumes to silence compatibility errors.

See [operations guidance](../../operations/operator-communications.md) and
[journal maintenance](../../operations/operator-journal.md) for the existing
backup/restore, privacy, retention and soft-removal boundaries.

## Implementation rulings

- Extend the existing call record, service, query hook and journal projections;
  retain independent same-mission conference/participation targets. This avoids
  duplicate persistence; stricter target equality remains outside this slice.
- Preserve fractional known durations and untouched timestamp precision; lead
  and shift controls require whole numbers. This retains old precise intervals
  while accepting fractional duration input.
- Require a start for new scheduled calls, while permitting unknown timing in
  legacy corrections. Such records remain explicitly unknown with no reminder.
- Keep the legacy compatibility tests in their existing module and integrate
  editor/synchronization tasks in one commit. This enlarges that review slice
  while keeping focused tests independent.
- Carry validated input on editor submission and retain raw numeric controls
  through store recovery. The callback differs from the initial plan signature
  to prevent stale-parent submission and draft loss.
- Treat stale Saved cues and wrong overdue statuses as correctness findings,
  despite their initial minor review grade, because they affect the operator's
  understanding of accepted state.
- Preserve the actor Docker endpoint. Host-approved dependency/cache access,
  Node 22.22.2 and explicit worktree tool PATH were needed locally. Production
  acceptance uses the provisioned Node binary directly so npm package metadata
  cannot leak into its offline nested command. These are tooling differences,
  not runtime configuration changes; versions and CI remain part of
  verification.
- Use the runner-required private project prefix and full 40-hex candidate SHA.
  Earlier rejected/failed runs retained evidence and removed their runtime
  resources. Browser selector fixes scope assertions to the intended editor,
  summary or call rather than hiding duplicate records with first-match queries.

## Cleanup and remaining gate

[Host cleanup proof](cleanup.json) supplements the runner's teardown report. The
acceptance runner reported and host checks verified no task containers,
networks, disposable volumes, child processes, image tags or listeners remain.
The open-PR worktree and evidence are retained; shared configuration,
credentials and unrelated resources were preserved. No aircraft validation or
merge is claimed. Final PR-head CI and product review remain the integration
gates.
