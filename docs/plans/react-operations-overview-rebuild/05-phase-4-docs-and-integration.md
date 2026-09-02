# Phase 4: Documentation and Integration

## Identity, input, and objective

Repository `bcl1713/starlink-dashboard`; durable PR
`https://github.com/bcl1713/starlink-dashboard/pull/143`; base `dev`; feature
`feature/react-operations-overview`. Reset baseline is
`07593c69040ad447000bf526d6453ec5c6faacfa`; historical SHA
`e649ce169cd5adcbdd83d6264290b30d5221599e` belongs at expected archive
`archive/pr-143-pre-simplification-e649ce1`.

Input is Oracle's exact Phase 3 accepted SHA and evidence manifest recorded in
`SESSION-HANDOFF.md`. Produce truthful operator/user/architecture/rollout docs,
receive independent documentation review, and hand Oracle an exact candidate for
integration to `dev`. Only Brian may authorize release to `main`.

## Product and scope contract

Follow [the product contract](00-product-contract.md). Documentation must
explain what exists, not the retired 2026-08-29 design:

- React overview purpose, route, live values, bounded local history, overlays,
  freshness/error behavior, and exact `1/2/5/10/30/paused` cadence controls;
- independent lanes, no overlap/catch-up burst, and manual refresh behavior;
- native 1920x1080 fullscreen entry/exit/fallback and no-scroll target;
- same-origin/security/CSP boundaries and no GEP public IP;
- Grafana remains available as fallback while React never requests it;
- simulation validation, troubleshooting, operational limits, rollback, and the
  exact Phase 3 evidence disposition.

**In:** user/operator docs, architecture/data-flow docs, navigation/index links,
troubleshooting, rollout/rollback, stale old claims, docs checks/review, and
`dev` integration handoff.

**Out:** feature changes unless a verified docs-blocking defect is routed back
to its owning phase, Grafana removal, feature scope expansion, direct merge to
`main`, release/tag/deployment, and unreviewed PR closure.

## Advisory paths after inspection

Likely, not binding:

- repository `README.md`
- `docs/design-document.md`
- `docs/index.md` or relevant documentation navigation
- `docs/setup/`, `docs/user-guide/`, `docs/troubleshooting/`
- `monitoring/README.md` and `monitoring/docs/`
- this roadmap and `SESSION-HANDOFF.md`

Inspect current docs, links, screenshots, and release policy first. Modify only
cohesive sources; do not create duplicate guides merely to avoid editing stale
ones. Keep each file at or below 300 lines unless repository policy records a
justified exception.

## Bounded task order

**TDD expectation:** Before editing prose, make the finite documentation
acceptance list and run link/claim checks to expose stale or missing coverage.
Each docs increment makes those focused checks GREEN. A product defect is not a
documentation RED; route it to its owning implementation phase.

1. **Pin inputs.** Verify clean exact Phase 3 SHA, read its manifest/handoff,
   and inventory all current references to Grafana, monitoring entry points,
   operations overview, refresh cadence, fullscreen, and rollback.
2. **Write doc acceptance list.** Before prose, create a finite checklist
   mapping each product bullet to an owning existing/new doc and audience.
   Identify contradictions and stale screenshots/commands.
3. **User guide.** Document route, panel/layer meaning, cadence values, paused
   and manual refresh, loading/stale/failure/recovery, accessibility, and native
   fullscreen controls/fallback using verified labels.
4. **Operator guide.** Document Nginx/same-origin topology, simulation smoke,
   health/status checks, browser troubleshooting, safe limits, CSP, no GEP IP,
   Grafana fallback, and rollback to the prior `dev` commit without deleting
   monitoring data.
5. **Architecture/security.** Record independent lane ownership,
   completion-based scheduling, bounded local ring buffers, `/api/status` hot
   path, overlay boundaries, no arbitrary PromQL/upstream URL, and Grafana
   non-dependency.
6. **Navigation and stale claims.** Add relative links from the proper indexes;
   remove claims that Grafana is being retired or that old global/history/
   viewport/evidence gates remain binding. Do not erase historical Git facts.
7. **Examples and screenshots.** Run every command shown or label environment-
   specific placeholders. Use only Phase 3 exact-head screenshots/evidence with
   source and accessibility text; do not invent outputs or future SHAs.
8. **Focused docs checks.** Format/lint changed Markdown and run the
   repository's link/naming checks plus a programmatic relative-link/anchor
   validator.
9. **Full checks.** Run docs/repository checks required for a docs-only final
   candidate and verify feature code is unchanged from accepted Phase 3 SHA.
10. **Independent reviews.** Obtain product/spec documentation review first,
    then editorial/quality review. The one writer addresses findings and reruns
    checks; reviewers do not edit.
11. **Commit and stop.** Create cohesive conventional docs commit(s), pin a
    clean exact SHA, and hand it to Oracle. Oracle verifies and integrates to
    `dev`; Brian separately decides whether/when `main` release begins.

## Exact checks

Focused checks are Prettier, markdownlint, naming, and relative-link/anchor
validation on changed Markdown. The repository docs tests, byte-identity check,
diff checks, and current CI/pre-commit check-only set form the full gate.

Use repository versions or bounded `npx` without changing package files:

```bash
npx prettier --check <changed-markdown-paths>
markdownlint-cli2 <changed-markdown-paths>
python3 tools/check_filename_convention.py
python3 <relative-link-and-anchor-validator> <changed-markdown-paths>
git diff --check <phase-3-sha>...HEAD
git diff --name-only <phase-3-sha>...HEAD
```

Run any repository docs/link tests found during inspection. Then run the minimal
full check set required by current CI/pre-commit in check-only mode. Verify
programmatically that non-documentation paths are byte-identical to the accepted
Phase 3 SHA. Record changed-file and line-count results.

## Independent gates

**Specification review first:** a documentation reviewer verifies every actual
control, label, cadence, source/freshness/failure behavior, fullscreen result,
security/privacy boundary, Grafana fallback, command, screenshot, rollback step,
and Phase 3 evidence reference against the exact candidate.

**Quality review second:** a separate pass checks audience fit, discoverability,
relative links/anchors, plain language, duplication, accessibility text, naming,
formatting, file size, and maintainability. Reviews identify SHA and do not
edit.

Any correction creates a new SHA and invalidates prior review disposition.
Feature defects return to the owning implementation phase and require renewed
acceptance rather than being concealed in prose.

## Public handoff, integration, and completion

Oracle's PR handoff includes PR/base/feature, Phase 3 input and Phase 4 output
SHAs, changed docs, documentation impact, commands/results, exact
runtime-evidence link, review dispositions, unresolved questions, rollback
summary, cleanup, and `next_step`.

Oracle may integrate only after exact-head checks and both doc reviews pass.
After integration, verify the `dev` commit contains the accepted feature and
docs and record the merge commit/public PR state. Do not delete the archive. Do
not remove Grafana. Do not merge/release to `main` without Brian's explicit
gate.

Completion means truthful discoverable docs, zero broken relative links/anchors,
reviewed immutable candidate, clean tree, and verified integration to `dev`.
Output is the `dev` integration SHA plus a Brian-facing release decision packet.
Stop; a `main` release is a separate session and authorization.
