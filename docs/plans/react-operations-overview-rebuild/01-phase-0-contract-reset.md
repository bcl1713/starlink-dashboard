# Phase 0: Contract and Branch Reset

## Identity and objective

Repository `bcl1713/starlink-dashboard`, durable PR
`https://github.com/bcl1713/starlink-dashboard/pull/143`, base `dev`, feature
`feature/react-operations-overview`. Historical head is
`e649ce169cd5adcbdd83d6264290b30d5221599e`; reset baseline is
`07593c69040ad447000bf526d6453ec5c6faacfa`; expected archive is
`archive/pr-143-pre-simplification-e649ce1`.

Create an executable docs-only contract from current `dev`. Oracle, not the
writer, archives the old remote head and publishes the exact reviewed candidate.
No production implementation begins in this phase.

## Scope

**In:** exactly the master roadmap and seven supporting files under
`docs/plans/react-operations-overview-rebuild/`; relative links, phase gates,
checks, and concrete Phase 1 handoff inputs.

**Out:** production/test/config/package changes, old plan copies, Docker,
GitHub/PR edits, pushes, archive/ref creation, and Phase 1 implementation.

The binding product contract is [the product contract](00-product-contract.md).
The old implementation is historical only; selective future salvage requires
deliberate review and never a wholesale cherry-pick.

## Likely paths

There are no advisory code paths in this docs-only phase. These paths are exact:

- `docs/plans/2026-09-02-react-operations-overview-rebuild.md`
- `docs/plans/react-operations-overview-rebuild/00-product-contract.md`
- `docs/plans/react-operations-overview-rebuild/01-phase-0-contract-reset.md`
- `docs/plans/react-operations-overview-rebuild/02-phase-1-live-data.md`
- `docs/plans/react-operations-overview-rebuild/03-phase-2-fullscreen-layout.md`
- `docs/plans/react-operations-overview-rebuild/04-phase-3-runtime-acceptance.md`
- `docs/plans/react-operations-overview-rebuild/05-phase-4-docs-and-integration.md`
- `docs/plans/react-operations-overview-rebuild/SESSION-HANDOFF.md`

## Bounded task order

**TDD expectation:** Phase 0 has no production code cycle. Treat formatting,
lint, link/anchor, line-limit, and exact-path validators as executable contract
tests: observe any failure, correct only the docs, and rerun before commit.

1. Verify clean branch `phase0/pr143-contract-reset` and exact baseline SHA.
2. Inspect repository naming, Markdown, line-size, and existing command policy.
3. Author only the eight paths above; keep each file at or below 300 lines.
4. Run Prettier in write mode only on those eight files, then check mode.
5. Run markdownlint only on those eight files.
6. Programmatically validate every relative Markdown target and heading anchor.
7. Run `git diff --check`, line counts, and exact changed-path assertions
   against `origin/dev`.
8. Commit once with `docs(plan): reset React overview implementation phases`.
9. Verify clean worktree, parent equals the baseline, and committed diff
   contains only the eight paths. Stop and hand the immutable SHA to Oracle.
10. Oracle arranges independent specification review, then documentation-quality
    review. Reviewers must not edit this worktree.
11. If review changes are needed, the sole writer adds a superseding local
    commit, reruns every check, and hands Oracle the new immutable SHA.

## Checks and expected results

The formatter/linter/link commands are the focused checks for changed docs. The
diff, line-count, and exact-path commands form the full Phase 0 gate.

Use installed repository tools when available; otherwise bounded `npx --yes`
commands may download tooling but must not change package files:

```bash
npx --yes prettier@3.6.2 --write <eight-paths>
npx --yes prettier@3.6.2 --check <eight-paths>
npx --yes markdownlint-cli2@0.19.1 <eight-paths>
git diff --check origin/dev...HEAD
git diff --name-only origin/dev...HEAD
wc -l <eight-paths>
```

The link/anchor validator must parse inline Markdown links, ignore external and
absolute URLs, resolve file/directory targets, GitHub-style slug headings, and
fail on a missing file or anchor. It must report eight checked files and zero
errors.

Exact path verification must compare a sorted generated list against the eight
listed paths, not rely on visual inspection. Confirm no retired old-plan file
and no production, test, config, package, lock, or Compose file appears.

A check-only pre-commit invocation is optional only when it can be constrained
to these files and will not mutate unrelated files. Do not use a fixer-bearing
all-files run for a documentation-only candidate.

## Review gate and public handoff

**Specification review:** independently compare every roadmap requirement,
identity/ref/SHA, phase boundary, security rule, retired gate, and handoff
field. Disposition is `PASS` or a finite findings list.

**Quality review:** after spec passes, independently check navigability,
self-contained session startup, actionable task sizes, unambiguous stop gates,
formatting, and duplication. Disposition is `PASS` or findings.

The Phase 0 public PR handoff, posted by Oracle, must state:

- PR/base/feature, exact candidate SHA, baseline and historical SHA;
- expected archive ref and publication procedure;
- eight changed paths, docs-only impact, and commands/results;
- spec/quality dispositions and unresolved questions;
- confirmation that no push/GitHub/Docker action occurred in the writer session;
- `next_step`: archive old head, force-update the existing feature ref to the
  reviewed docs-only candidate, verify remote exact SHA/diff, then open a new
  Phase 1 session from that published head.

## Documentation impact, cleanup, and completion

Documentation impact is this roadmap only; no operator/user behavior changed.
Remove any formatter cache or temporary validator artifact. Local-writer
completion requires one local commit, clean status, exact parent baseline, exact
eight-file diff, and all checks green. Oracle may publish only after independent
specification then quality approval of that immutable commit.

Stop after handoff. Phase 1 input is the Oracle-published Phase 0 SHA, not the
local baseline and not a guessed value. Phase 1 output is defined in
[Phase 1](02-phase-1-live-data.md).
