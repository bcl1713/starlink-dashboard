# Quality Gates

This guide is the authoritative command reference for local verification and
continuous integration. Run the commands from the repository root.

## Prerequisites

- CI bootstraps Python 3.11 from the backend's tracked `.python-version`,
  matching production. Both Python jobs pass setup-python's executable to uv
  and disable uv Python downloads, so uv reuses that installation. Locally,
  `tools/verify` uses the tracked selection unless `UV_PYTHON` is supplied.
- The backend uses one uv dependency environment with both
  `requirements-dev.txt` (including application requirements) and
  `requirements-gfs.txt`. Static retains its development dependency install
  for root policy tests; Black and Ruff use uv with the same Python selection.
  Backend commands also consume the generated hashed `requirements-ci.txt` and
  reject stale source fingerprints before uv. CI pins uv 0.12.19 and uses
  separate static/backend caches keyed by OS, architecture, actual Python patch,
  uv, all backend requirements, and tracked Python. See the
  [measurement and regeneration guide](../development/ci-404/completion.md).
- Use Node 22.22.2 or a newer Node 22 patch. CI uses 22.22.2, and the frontend
  package declares that Node 22 range. Older patches do not satisfy the locked
  jsdom dependency requirements. Install locked frontend dependencies with
  `npm ci` from `frontend/mission-planner` before running frontend or static
  checks.
- Install the static executables `markdownlint-cli2` and `Lychee`, which are
  required for Markdown formatting and documentation-link validation.

## Canonical Commands

```bash
ACCEPTANCE_POLICY_BASE_SHA=$(git merge-base origin/dev HEAD) ./tools/verify static
./tools/verify backend
./tools/verify frontend
./tools/verify all
```

`ACCEPTANCE_POLICY_BASE_SHA` must be an exact reachable 40-hex ancestor SHA;
static/all use it to inspect the candidate delta for typing-policy violations.
Supply the same variable for `./tools/verify all`. CI provides its reviewed
base. For task runs, wrap commands in a wall-clock bound, for example
`timeout --kill-after=10s 10m ./tools/verify static` with that variable set.
Record task ownership before starting workers and verify teardown afterward; see
[resource lifecycle](../development/workflow.md#resource-lifecycle-for-every-tier).

Use the narrowest tier that covers the change while developing. Before a pull
request is ready, run the applicable tier or `./tools/verify all`.

- `static` runs formatting and linting checks, filename conventions, Markdown
  formatting, and documentation link validation. Internal files and anchors are
  required; external HTTP/HTTPS failures are reported as nonblocking warnings.
- `backend` runs the complete backend pytest suite from its established
  `backend/starlink-location` context. It first prints the actual Python
  executable/version and installed distribution versions using the same uv
  requirement inputs, then reports the 50 slowest pytest phases (including
  setup/teardown). Each command prints elapsed seconds and its exit status.
  CI runs four isolated whole-file shards, each with a 20-minute command limit,
  ten-second forced-kill grace, and 25-minute job cap. The reported-run owner
  cleans private stores and verified descendants before evidence upload.
  Compare environment/inventory time separately from pytest time and the
  GitHub job setup/post steps; pytest retains collection/pass/skip totals.
- `frontend` runs Vitest with `npm run test:unit` and then the frontend
  production build.
- `all` runs `static`, `backend`, and `frontend` in that order, stopping at the
  first failure.

The commands resolve their own working directories. Do not replace them with
similar commands from another directory: root-relative static and frontend
commands and the backend pytest context are deliberate parts of the contract.

## Documentation Link Policy

The static tier runs `python3 tools/check_docs_links.py docs/` in two passes:

1. **Required internal links:** Lychee runs offline with the `file` scheme,
   fragment checks and an explicit file inclusion that overrides the legacy
   `.lycheeignore` file exclusion. Missing files, broken anchors, invalid
   inputs, a missing checker or an internal-check timeout fail the static gate.
2. **Advisory external links:** HTTP/HTTPS checks retain normal failure reports
   and emit a CI warning, but remote timeouts, TLS errors, rate limits and other
   external failures do not fail the gate. Each request has a ten-second limit
   with no retry; each pass has a two-minute process limit.

This is the repository's accepted external-link failure policy. It does not
waive formatting, lint, internal-link validation, typing-policy tests or other
required checks. The regression tests exercise missing local files, missing
anchors, ignore-file bypass and an unreachable local HTTP target without needing
an external service. CI continues to call the same canonical static command.

## CI Mapping

Normal CI keeps Static Quality Gate, Backend Test Gate, and Frontend Test and
Build Gate. Four explicit `backend_1` through `backend_4` jobs run the complete
collection and retain their disjoint whole-file assignments. Backend Test Gate
always evaluates all four prerequisites and requires complete matching artifacts,
coverage, outcomes, runtime identities, and cleanup; uploaded diagnostics cannot
turn failed execution green. Static also runs the mandatory source-controlled
backend shard, gate CLI, verifier, workflow, and lifecycle contracts.

For isolated local shard and aggregate commands, report identity, private-root
ownership, measured timing limits, and rollback to serial, see
[backend CI completion](../development/ci-404/completion.md). Use separate full
worktrees and fresh roots for concurrent local shards. Plain `backend` and `all`
remain complete serial fallback commands.

## Browser and Runtime Boundary

For browser-relevant changes, complete exact-SHA CDP acceptance at 1920x1080 in
addition to the applicable verification tier. A green `./tools/verify all` does
not substitute for browser or runtime evidence. Browser acceptance remains
change-scoped rather than a generic CI or runtime replacement.

## Related Guides

- [Testing Guide](testing-guide.md) for focused backend and frontend examples.
- [Contributing Guide](../../CONTRIBUTING.md) for workflow and pull-request
  expectations.
