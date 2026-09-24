# Quality Gates

This guide is the authoritative command reference for local verification and
continuous integration. Run the commands from the repository root.

## Prerequisites

- Use the project-supported Python 3.13 and `uv`; the Python tiers load
  `backend/starlink-location/requirements-dev.txt` through `uv run`.
- Use Node 22.12.0. Install locked frontend dependencies with `npm ci` from
  `frontend/mission-planner` before running frontend or static checks.
- Install the static executables `markdownlint-cli2` and `Lychee`, which are
  required for Markdown formatting and documentation-link validation.

## Canonical Commands

```bash
./tools/verify static
./tools/verify backend
./tools/verify frontend
./tools/verify all
```

Use the narrowest tier that covers the change while developing. Before a pull
request is ready, run the applicable tier or `./tools/verify all`.

- `static` runs formatting and linting checks, filename conventions, Markdown
  formatting, and documentation link validation.
- `backend` runs the complete backend pytest suite from its established
  `backend/starlink-location` context.
- `frontend` runs Vitest with `npm run test:unit` and then the frontend
  production build.
- `all` runs `static`, `backend`, and `frontend` in that order, stopping at the
  first failure.

The commands resolve their own working directories. Do not replace them with
similar commands from another directory: root-relative static and frontend
commands and the backend pytest context are deliberate parts of the contract.

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
