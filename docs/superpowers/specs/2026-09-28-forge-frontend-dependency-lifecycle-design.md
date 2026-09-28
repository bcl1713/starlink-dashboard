# Forge Frontend Dependency Lifecycle Design

## Purpose

A clean Forge checkout must satisfy all acceptance phases without relying on a
leftover `node_modules` directory from an earlier branch. The platform browser
card imports `@playwright/test` during health, frontend static checks require
`eslint` and Vitest, and final acceptance creates a separate task-owned
worktree. Each of those boundaries needs a deliberate dependency lifecycle.

The goal is deterministic, least-privilege frontend dependency preparation on
Forge while preserving the acceptance platform's separation between
platform-owned operations and product-owned TOML semantics.

## Evidence

The exact clean Forge candidate
`380ab942310370be1e92b12a09cfba561744ee3d` reached a sealed
`environment_blocked` health outcome. The health card failed with:

```text
Error: Cannot find module '@playwright/test'
```

The earlier final candidate reached its backend static success but failed at:

```text
> mission-planner@0.0.0 lint
> eslint .
sh: 1: eslint: not found
```

This is not an application defect. It is an incomplete candidate-bootstrap
workflow. The authoritative quality-gate guide already requires frontend
dependencies before frontend/static commands, and the external-host runbook
says to install ordinary project dependencies before the lanes, but neither
identifies the exact safe command nor accounts for the final wrapper's fresh
worktree.

## Scope

This change owns only acceptance-platform dependency preparation and its
operator documentation.

It includes:

- explicit Forge candidate-bootstrap instructions before health;
- one platform-owned frontend dependency preparation step in the Python final
  runner after health validation and before declared static checks or browser
  launch; and
- cleanup validation that recognizes only the final runner's generated frontend
  `node_modules` directory as task content.

It does not change product contracts, application dependencies, Dockerfiles,
CI tiers, browser provisioning, candidate image construction, the visible
journey, retry policy, or branch/operator credentials.

## Decision

### Candidate checkout before health and static

The external-host runbook must name the exact command, run in the checked-out
candidate's frontend directory:

```bash
env CI=1 npm ci --ignore-scripts
```

It occurs after exact SHA/ref verification and before health. `--ignore-scripts`
prevents branch-controlled lifecycle scripts from acting as a Playwright or
Chromium installer. It still installs the lockfile-resolved packages needed by
the health card, ESLint, and Vitest. The operator must not substitute `npm
install`, `npx`, a browser installer, or a pre-existing checkout's
`node_modules` directory.

The initial candidate checkout is retained for the health/static sequence, so
this runs once for those two lanes.

### Final task worktree

The final wrapper creates a new, disposable worktree. The Python final runner
already performs declared static checks before it launches the task-owned
browser. After health validation and before those checks, it must prepare the
frontend dependency group once with the literal command:

```bash
env CI=1 npm ci --ignore-scripts
```

This is platform-owned operational authority: it is not expressed in product
TOML and no caller can replace its package manager, arguments, working
directory, or timing. The separate `static` lane must not repeat the command;
it reuses the operator-prepared candidate checkout.

A nonzero result fails the final lane before Python static checks, Docker, Xvfb,
browser launch, or runtime work. The runner seals the failure through its
existing final evidence and cleanup path, classifying it as a platform
preparation failure rather than a product assertion failure.

### Cleanup

The wrapper-created `frontend/mission-planner/node_modules` directory is the
only generated path excluded from the final worktree's clean-tree validation.
It remains inside the task-owned worktree and is removed by the existing exact
worktree removal. No broad `git clean`, global npm cache clearing, Docker
pruning, or deletion outside the runner checkout is permitted.

### Existing partial repair

Commit `380ab942310370be1e92b12a09cfba561744ee3d` established the needed
frontend-install regression seam, but its unconditional `npm ci` inside the
shared static executor is superseded. The implementation must make the same
safe command a final-lane-only preparation step after health validation,
leaving a separately invoked `static` lane to reuse the operator-prepared
candidate checkout.

## Data flow

1. The branch operator verifies the remote exact SHA/ref and prepares frontend
dependencies in the initial Forge checkout.
2. Health uses those dependencies for the platform card and seals its normal
fingerprint.
3. Static reuses the same prepared checkout.
4. Final validates the health fingerprint, allocates a task-owned worktree, then
   its Python runner prepares frontend dependencies before declared static checks.
5. The runner performs declared static checks, build, controls, and browser
   journey as today.
6. The wrapper validates and removes only its task-owned worktree. Evidence
remains outside it.

## Tests and acceptance criteria

Tests must prove all of the following:

- final-only preparation runs exactly `env CI=1 npm ci --ignore-scripts` after
  health validation and before static checks or browser startup;
- dependency-preparation failure prevents declared static checks, browser launch,
  Docker, controls, and the journey, and yields sealed non-final evidence;
- a final worktree containing only the final runner's frontend `node_modules`
  directory still passes the ownership/cleanliness check and is removed;
- other untracked files still block removal;
- the runner's static executor only executes contract-declared static commands
  and does not perform an extra npm installation;
- operator documentation names the exact host bootstrap command and ordering;
- existing health/static/final isolation, evidence, cleanup, and no-retry rules
  remain unchanged.

Acceptance requires a new pushed exact SHA and the Forge health → static → one
final sequence. The final evidence must be sealed, claim `passed` and
`final_acceptance: true`, and include verified cleanup. A failed final consumes
its attempt and cannot be retried without explicit authorization and fresh
health/static evidence.

## Non-goals

- No shared or remote npm cache service.
- No browser download or Playwright installation during branch acceptance.
- No inferred or user-supplied package-manager command.
- No local Docker, Vite, or standalone Playwright run treated as acceptance.
- No changes to issue #177 product behavior.
