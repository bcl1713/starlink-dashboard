# Quality-Gate Contract Design

**Purpose:** Make local verification and GitHub Actions execute the same
repository-root commands, with explicit tiered coverage and pinned developer
formatting/lint tools.

## Problem

Issue #179 exposed a verification-context mismatch. Running Ruff from
`backend/starlink-location` with `ruff check app tests` classifies `app`
differently from the existing CI command, which runs from repository root with
backend-relative paths. Both invocations can be locally green while disagreeing
about import order.

The current workflow duplicates shell commands rather than invoking a
repository-owned contract. It runs static checks but does not run the backend
pytest suite, frontend Vitest suite, or frontend production build. Contributor
documentation is inconsistent: `CONTRIBUTING.md` still names `main` as the
branch base, testing guides show commands that do not match package scripts,
and neither documents CI's exact root-relative static gate. Black and Ruff are
installed without version pins in CI.

## Scope

This change creates one canonical verification interface and updates CI and
contributor documentation to use it.

It covers:

- repository-root static verification;
- backend pytest verification;
- frontend Vitest and production-build verification;
- an explicit browser-acceptance handoff rather than an unconditional browser
  job;
- deterministic Black and Ruff versions in a development-only manifest;
- CI and documentation migration to the canonical commands.

It does not add Docker runtime rebuilds, browser acceptance, deployment, or
release publication to every pull request. Those remain change-specific gates.

## Canonical Verification Interface

Add an executable repository-owned command interface at `tools/verify`.
It must resolve the repository root from its own location, reject unknown tier
names, and execute every child command from that root. Callers must not depend
on their current working directory.

The interface accepts exactly these tiers:

- `static` runs the existing static quality checks with root-relative targets:
  Black and Ruff for `backend/starlink-location/app` and `tests`; filename
  conventions; frontend Prettier and ESLint; Markdownlint for `docs`; and
  Lychee for `docs`.
- `backend` runs the backend suite from `backend/starlink-location` using the
  declared development requirements.
- `frontend` runs `npm run test:unit` and `npm run build` from
  `frontend/mission-planner` after its locked frontend dependencies are
  installed.
- `all` runs `static`, `backend`, and `frontend` in that order and stops at the
  first failing tier.

The command prints each invoked command before executing it and preserves its
exit status. It is the only source of static/backend/frontend command text for
CI and contributor documentation.

## Toolchain Contract

Add `backend/starlink-location/requirements-dev.txt`. It includes the existing
runtime/test requirements and pins the formatter/linter versions used by the
root static tier:

```text
-r requirements.txt
black==26.5.1
ruff==0.16.8
```

The manifest is development-only. Production Docker dependency installation
continues to use `requirements.txt`; development tools must not be added to the
production image solely to satisfy CI.

The interface uses `uv run --with-requirements
backend/starlink-location/requirements-dev.txt` for Python static and backend
commands. CI uses the same file with `pip install -r`, then invokes
`tools/verify`; exact tool versions and command targets therefore remain shared.
This pins the tools responsible for the known classification/format contract.
It does not claim a full lockfile for every transitive runtime dependency.

## CI Contract

Replace duplicated individual quality commands in `.github/workflows/lint.yml`
with named jobs that call the canonical interface:

- `static`: set up Python 3.13 and Node 22.12.0, install the declared Python
  development requirements and locked frontend dependencies, then run
  `tools/verify static`.
- `backend`: set up Python 3.13, install the declared Python development
  requirements, then run `tools/verify backend`.
- `frontend`: set up Node 22.12.0, install frontend dependencies with the
  existing lockfile, then run `tools/verify frontend`.

Each job runs for pull requests and pushes to `main` and `dev`, preserving the
current routing. A failing child command fails its named job directly; the
workflow must not use `continue-on-error` plus a hand-maintained summary as a
substitute for a required check.

The existing GHCR publication workflow remains separate. A successful quality
workflow is not deployment evidence.

## Browser Acceptance Boundary

`tools/verify` must not silently launch browser acceptance. The exact-SHA
1920x1080 CDP browser standard remains mandatory when the approved task changes
browser-relevant behavior. Its invocation, candidate SHA, evidence, and
coverage remain governed by the existing browser-acceptance workflow rather
than being reduced to a generic CI smoke test.

The contributor guide names this boundary explicitly: static/backend/frontend
jobs prove their respective tiers; they do not prove runtime or browser
acceptance.

## Documentation

Update these documents in the implementation PR:

- `CONTRIBUTING.md`: identify `dev` as the integration branch; replace vague
  testing bullets with `tools/verify` tiers and the browser-acceptance boundary.
- `docs/contributing/testing-guide.md`: replace stale `npm test` examples with
  the real `npm run test:unit` command and link to the canonical tier commands.
- `backend/starlink-location/README.md` and
  `backend/starlink-location/docs/TESTING.md`: retain focused pytest examples,
  but designate `tools/verify backend` as the canonical full backend gate.
- Add `docs/contributing/quality-gates.md` as the concise operator/developer
  reference for tier purpose, prerequisites, CI mapping, and browser boundary.

No user-facing product documentation, API documentation, release note, or
runtime runbook changes are required.

## Failure Handling

The interface fails closed:

- an invalid tier returns a nonzero status and lists supported tiers;
- a missing required executable or dependency returns the literal child-command
  failure rather than substituting an unrelated command;
- each tier stops at the first failing command and preserves that command's
  exit status;
- CI reports the failed tier as the failing job, without converting failure to
  a green workflow summary.

A static failure found only by a broader or different command than the declared
tier is recorded as a separate maintenance finding, not silently folded into an
unrelated change's acceptance claim.

## Verification

1. Automated tests cover repository-root discovery from a nested current
   directory, tier dispatch, invalid-tier rejection, command ordering, and
   preservation of a failing child exit status. They must prove that the static
   tier invokes the exact backend-relative Black and Ruff targets used by CI.
2. The static tier runs clean on the implementation head from both repository
   root and a nested directory, proving caller working directory cannot recreate
   #179's import-classification mismatch.
3. The backend tier runs the complete pytest suite; the frontend tier runs
   Vitest and the TypeScript/Vite production build.
4. CI runs all three named jobs on the exact PR head. The PR report names each
   job and its result.
5. Independent task review and final whole-branch review verify that CI contains
   no duplicated quality-command implementation and that development tools stay
   out of production requirements/Dockerfiles.
6. Browser acceptance is explicitly classified as not applicable for this
   verification-contract maintenance change. No browser/runtime evidence is
   claimed.

## Non-Goals

- Replacing the frontend package manager or lockfile.
- Introducing a full Python dependency lockfile or packaging migration.
- Adding Docker builds, health checks, or browser journeys to every pull
  request.
- Changing the existing exact-SHA browser acceptance standard.
- Making quality checks pass by weakening Ruff, Black, ESLint, or test rules.
