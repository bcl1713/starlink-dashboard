# Quality Gates

This guide is the authoritative command reference for local verification and
continuous integration. Run the commands from the repository root.

## Prerequisites

- CI bootstraps Python 3.13 and `uv`. The backend context currently pins Python
  3.11 in `.python-version`, matching its production Docker runtime; `uv run`
  respects that tracked selection. The Python tiers load
  `backend/starlink-location/requirements-dev.txt` through `uv run`.
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
  `backend/starlink-location` context.
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

Normal CI runs the static, backend, and frontend tiers as separate required
jobs. The repository-owned commands above are the shared command interface for
contributors and CI.

## Browser and Runtime Boundary

For browser-relevant changes, complete exact-SHA CDP acceptance at 1920x1080 in
addition to the applicable verification tier. A green `./tools/verify all` does
not substitute for browser or runtime evidence. Browser acceptance remains
change-scoped rather than a generic CI or runtime replacement.

## Related Guides

- [Testing Guide](testing-guide.md) for focused backend and frontend examples.
- [Contributing Guide](../../CONTRIBUTING.md) for workflow and pull-request
  expectations.
