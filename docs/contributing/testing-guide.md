# Testing Guide

[Back to Contributing](../../CONTRIBUTING.md)

The [Quality Gates](quality-gates.md) guide is the authoritative reference for
the repository-wide verification tiers.

---

## Backend Tests (Python)

```bash
# Run the full canonical backend gate from the repository root
./tools/verify backend

# Run focused backend tests from the existing backend context
cd backend/starlink-location

# Run tests with coverage
pytest --cov=app tests/

# Run specific test file
pytest tests/test_routes.py

# Run specific test
pytest tests/test_routes.py::test_get_routes
```

**Test Requirements:**

- New features should include corresponding tests
- Tests must pass before merge
- Maintain >80% code coverage for refactored code

---

## Frontend Tests (TypeScript/React)

```bash
cd frontend/mission-planner

# Run unit tests
npm run test:unit

# Run tests with coverage
npm run test:unit -- --coverage
```

Use `./tools/verify frontend` from the repository root for the canonical
frontend gate; it runs the unit suite and production build.

### Three.js component tests

Use `@react-three/test-renderer` for components that return Fiber elements such
as `group` and `primitive`. React DOM treats these as unknown HTML elements and
cannot verify their attachment to a Three.js scene. The Vitest-only ESM aliases
keep the native renderer and application on the same Three.js instance.

The `AnimatedFlowLine` lifecycle tests advance the real Fiber frame subscribers
and retain their particle, pause, buffer reuse, and exact-once disposal checks.
For the StrictMode probes, the test helper enables the real reconciler's strict
root flag: React 19 otherwise treats the StrictMode inside Fiber's Provider as
nested and does not replay its effects. Do not reduce the allocation/disposal
expectations to accommodate that harness difference.

### Investigating warnings

Capture warnings directly when auditing a passing suite:

```bash
npm run test:unit -- --disableConsoleIntercept
NODE_OPTIONS=--trace-warnings npm run build
```

Keep warnings visible; do not add blanket console filters or disable Node
deprecations. The native renderer currently exposes Fiber 9.7.0's use of
deprecated `THREE.Clock` with Three.js 0.185.1. Its clock migration belongs in
the upstream dependency path; these tests drive frames explicitly.

The unchanged `OverviewPage.traffic.test.tsx` Canvas mock still renders scene
children inside a `div`. A full warning capture therefore also reports scene tag
casing/recognition and shader-property attribute warnings from that file. The
`AnimatedFlowLine` migration resolves its own DOM warnings; it does not make the
entire frontend suite warning-free.

The locked `@tailwindcss/node` 4.1.17 calls `module.register()` for its ESM
cache loader. Node 26 emits DEP0205 for that call; the supported Node 22
baseline does not. Vite 7.3.6 already prefers `registerHooks()` where available.
Recheck Tailwind's loader when changing the supported Node major instead of
patching Node's module API or suppressing the warning.

The production build still reports a large JavaScript chunk. A chunk size
advisory alone does not establish a runtime performance failure. Measure cold
load, route navigation, and the Overview workload before choosing lazy loading
or manual chunk boundaries; keep the advisory threshold intact.

---

## Pull Request Guidelines

### PR Title Format

```text
<type>: <description>

Types: feat, fix, refactor, docs, test, chore
```

### PR Description Template

```markdown
## Changes

Brief description of what changed and why.

## Testing

How was this tested? Include manual smoke tests or automated test commands.

## Checklist

- [ ] Code passes linting (Black, Ruff, Prettier, ESLint)
- [ ] Existing tests pass
- [ ] New tests added (if applicable)
- [ ] Documentation updated (if applicable)
- [ ] No breaking changes introduced
```

---

[Back to Contributing](../../CONTRIBUTING.md)
