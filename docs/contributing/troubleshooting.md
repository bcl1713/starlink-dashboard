# Contributing Troubleshooting

[Back to Contributing](../../CONTRIBUTING.md)

---

## Pre-commit Hooks Not Running

```bash
# Reinstall hooks
pre-commit install

# Verify hooks are installed
cat .git/hooks/pre-commit
```

---

## Linting Failures Don't Match CI

```bash
# Install the committed backend formatter/linter versions used by CI
pip install --requirement backend/starlink-location/requirements-dev.txt
cd frontend/mission-planner
npm update prettier eslint
npm install -g markdownlint-cli2@latest
```

The backend Black and Ruff versions are pinned in
`backend/starlink-location/requirements-dev.txt`. Reinstall from that manifest
instead of upgrading those tools independently.

---

## Black and Ruff Conflict

Black and Ruff are configured to work together without conflicts. If you see
conflicting suggestions, reinstall both from the committed dev-tool manifest.

---

## ESLint or Prettier Not Found

```bash
cd frontend/mission-planner
npm install
```

---

## Getting Help

- Check existing issues and PRs for similar problems
- Review linting tool documentation:
  - [Black](https://github.com/psf/black)
  - [Ruff](https://docs.astral.sh/ruff/)
  - [Prettier](https://prettier.io/)
  - [ESLint](https://eslint.org/)
  - [Markdownlint](https://github.com/igorshubovych/markdownlint-cli)

---

## Questions?

For questions about development process, code quality standards, or tooling,
open an issue or discussion on the project repository.

---

[Back to Contributing](../../CONTRIBUTING.md)
