# Markdownlint Documentation Repair — Implementer Report

## Scope and result

Implemented the content-preserving Markdown repair for the nine named documents.
All requirements and decisions remain in the repaired plans/specifications; changes
are line reflow, required list spacing, and navigation-preserving plan splits.
No product code, tests, tools, CI configuration, or unrelated documentation was
committed.

Documentation cleanup commit:
`f69ecce2a05a3f2630d0660937ed35e312d4d1a3`
(`docs: repair markdown lint violations`).

## Documents changed

- `docs/operations/acceptance-platform.md`
- `docs/superpowers/plans/2026-09-23-v2-mission-retirement-acceptance-runbook.md`
- `docs/superpowers/plans/2026-09-24-v2-acceptance-browser-recovery.md`
- `docs/superpowers/plans/2026-09-25-acceptance-platform-structural-typing.md`
- `docs/superpowers/plans/2026-09-25-v2-content-aware-final-build.md`
- `docs/superpowers/plans/2026-09-25-v2-upcoming-pois-webgl.md`
- `docs/superpowers/specs/2026-09-24-v2-acceptance-browser-recovery-design.md`
- `docs/superpowers/specs/2026-09-25-v2-content-aware-final-build-design.md`
- `docs/superpowers/specs/2026-09-25-v2-upcoming-pois-webgl-design.md`

Each changed document was reflowed to the configured 80-character MD013 limit.
Required blank lines around lists were added for MD032. Code blocks, heading text,
requirements, decisions, commands, and examples were retained.

## Created companion documents and split boundaries

Every main plan links to its companion documents, and every companion links back
to its main plan. A verification pass compared all original top-level task labels
with the assembled main-plus-companion documents; every original task label was
present exactly in the resulting navigation set.

- The V2 mission-retirement acceptance runbook splits after its introduction:
  - `...-tasks-1-2.md`: Tasks 1–2 (model/artifact and Compose contracts).
  - `...-tasks-3-4.md`: Tasks 3–4 (browser card and staged runner).
  - `...-tasks-5-6.md`: Tasks 5–6, self-review, and documentation impact.
- The content-aware final-build plan keeps Task 1 in the main plan and moves
  Tasks 2–4 to `2026-09-25-v2-content-aware-final-build-task-2-4.md`.
- The V2 upcoming-POIs/WebGL plan keeps Task 1 in the main plan, moves Tasks 2–3
  to `...-tasks-2-3.md`, and moves Task 4/final verification to `...-task-4.md`.
- The V2 acceptance-browser-recovery plan was also split after reflow, because
  reflow took it from 266 to 358 lines and therefore above the 300-line rule:
  `...-tasks-1-2.md` and `...-tasks-3-4.md` retain Tasks 1–4.
- The structural-typing plan similarly rose from 225 to 302 lines after required
  reflow. It now uses `...-tasks-1-2.md` and `...-task-3.md`.

All resulting plan documents are at or below 300 lines; the largest is the
content-aware companion at 276 lines.

## Commands and results

Passed:

```text
markdownlint-cli2 'docs/**/*.md'
```

Result: `Linting: 233 files`, `Summary: 0 issues in 0 files`.

Passed:

```text
git diff --check
```

Result: no output and exit status 0 before the documentation commit.

Ran exactly:

```text
ACCEPTANCE_POLICY_BASE_SHA="$(git merge-base origin/dev HEAD)" ./tools/verify static
```

The static verifier completed Black, Ruff, filename conventions, Prettier,
frontend ESLint, and its own Markdownlint invocation successfully. It then
blocked at the first unavailable required executable:

```text
(/home/brian/starlink-dashboard-v2-mission-retirement) $ lychee --no-progress docs/
FileNotFoundError: [Errno 2] No such file or directory: 'lychee'
```

No installation or verification-tool change was made; that would exceed the
approved documentation-only scope.

## Preserved workspace state and blockers

Existing modified and untracked report files were not staged, changed, or
removed. The only blocking verification issue is the missing `lychee` executable
in the current environment. There are no Markdownlint or whitespace blockers.
