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
