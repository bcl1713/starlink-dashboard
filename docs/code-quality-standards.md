# Code Quality Standards

This document outlines code quality standards, linting tools, and automated
checks for the Starlink Dashboard project.

## Overview

The project enforces consistent code quality through automated linting and
formatting tools. All code must pass these checks before merge.

---

## Python Code Quality

### Python Tools

- **Black**: Automatic code formatting (88 char line length)
- **Ruff**: Fast Python linter (syntax, security, style checks)

### Python Configuration

- Black configuration: Project-level defaults (88 char limit)
- Ruff configuration: `.ruff.toml` (if present) or project defaults
- Python version: 3.13

### Python Local Usage

```bash
# Format with Black
black backend/starlink-location/app

# Lint with Ruff
ruff check backend/starlink-location/app

# Auto-fix Ruff violations
ruff check --fix backend/starlink-location/app
```

---

## JavaScript/TypeScript Code Quality

### TypeScript Tools

- **Prettier**: Automatic code formatter (80 char print width, prose wrap)
- **ESLint**: Static analysis for bugs and style issues

### TypeScript Configuration

- Prettier: `.prettierrc` (print width 80, prose wrap always)
- ESLint: `frontend/mission-planner/.eslintrc.json`
- Node version: 18.17.1

### TypeScript Local Usage

```bash
cd frontend/mission-planner

# Format with Prettier
npx prettier --write "src/**/*.{ts,tsx,js,jsx}"

# Lint with ESLint
npx eslint src --ext .ts,.tsx

# Auto-fix ESLint violations
npx eslint src --ext .ts,.tsx --fix
```

---

## Markdown Documentation Quality

### Markdown Tools

- **Prettier**: Markdown formatting (80 char print width, prose wrap)
- **Markdownlint-cli2**: Markdown linting (style and consistency checks)

### Markdown Configuration

- Prettier: `.prettierrc` (shared config)
- Markdownlint: `.markdownlint.jsonc` (if present) or defaults

### Markdown Local Usage

```bash
# Format with Prettier
npx prettier --write "docs/**/*.md"

# Lint with Markdownlint
markdownlint-cli2 "docs/**/*.md"
```

---

## Pre-commit Hooks

The project uses pre-commit hooks to automatically run linting tools before each
commit, ensuring code quality is enforced locally.

### Installation

```bash
# Install pre-commit framework
pip install pre-commit

# Install git hooks in this repository
pre-commit install
```

### What Runs on Commit

When you run `git commit`, the following tools run automatically:

- Black (Python formatting)
- Ruff (Python linting)
- Prettier (JavaScript/TypeScript/Markdown formatting)
- ESLint (JavaScript/TypeScript linting)
- Markdownlint (Markdown linting)

### Bypassing Pre-commit Hooks

If necessary, you can bypass pre-commit hooks (not recommended):

```bash
git commit --no-verify
```

---

## CI/CD Linting Pipeline

GitHub Actions automatically runs linting checks on all pull requests and
pushes. Checks are defined in `.github/workflows/lint.yml`.

### CI Pipeline includes

- Black formatting check
- Ruff linting check
- Prettier formatting check
- ESLint check
- Markdownlint check

### Status Checks

- All checks must pass before merging to main/develop branches
- Check status appears in PR conversation

---

## Code Style Guidelines

### Python Files

- **File Size**: Prefer files under 300 lines; split large files into modules
- **Line Length**: 88 characters (Black default)
- **Type Hints**: Add type hints to all function parameters and returns
- **Docstrings**: Use PEP 257 format for all public functions and classes
- **Comments**: Explain "why" not "what"; comments should clarify intent
- **Names**: Use descriptive names for variables, functions, and classes

### TypeScript/JavaScript Files

- **File Size**: Prefer files under 300 lines; extract sub-components
- **Line Length**: 80 characters (Prettier config)
- **Type Annotations**: Use TypeScript types; avoid `any`
- **JSDoc**: Add JSDoc comments to exported functions
- **Comments**: Explain "why" not "what"
- **Names**: Use camelCase for variables/functions, PascalCase for components

### Markdown Files

- **File Size**: Prefer files under 300 lines; split into sub-documents
- **Line Length**: 80 characters with prose wrap
- **Links**: Use relative paths for links within docs/
- **Code Blocks**: Include language identifier (python, bash, typescript)
- **Headings**: Use consistent heading hierarchy (no h1 jump to h3)

---

## Troubleshooting

### Pre-commit Hooks Not Running

```bash
# Reinstall hooks
pre-commit install

# Verify hooks are installed
cat .git/hooks/pre-commit
```

### Linting Failures Don't Match CI

```bash
# Update tools to match CI versions
pip install --upgrade black ruff
cd frontend/mission-planner
npm update prettier eslint
npm install -g markdownlint-cli2@latest
```

### Black and Ruff Conflict

Black and Ruff are configured to work together without conflicts. If you see
conflicting suggestions, ensure both tools are up-to-date.

### ESLint or Prettier Not Found

```bash
cd frontend/mission-planner
npm install
```

---

## Utility Commands

### Format All Code

```bash
# Python
black backend/starlink-location/app
ruff check --fix backend/starlink-location/app

# JavaScript/TypeScript
cd frontend/mission-planner
npx prettier --write "src/**/*.{ts,tsx,js,jsx}"

# Markdown
npx prettier --write "docs/**/*.md"
```

### Check Linting Without Formatting

```bash
# Python
black --check backend/starlink-location/app
ruff check backend/starlink-location/app

# JavaScript/TypeScript
cd frontend/mission-planner
npx prettier --check "src/**/*.{ts,tsx,js,jsx}"
npx eslint src

# Markdown
npx prettier --check "docs/**/*.md"
markdownlint-cli2 "docs/**/*.md"
```

### Run Local Pre-commit Checks

```bash
# Run all hooks on staged files
pre-commit run

# Run all hooks on all files
pre-commit run --all-files

# Run specific hook
pre-commit run black --all-files
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
