# Code Quality Standards

[Back to Contributing](../../CONTRIBUTING.md)

---

## Overview

The project enforces consistent code quality through automated linting and
formatting tools. All code must pass these checks before merge.

---

## Python Code Quality

**Tools:**

- **Black**: Automatic code formatting (88 char line length)
- **Ruff**: Fast Python linter (syntax, security, style checks)

**Configuration:**

- Black configuration: Project-level defaults (88 char limit)
- Ruff configuration: `.ruff.toml` (if present) or project defaults
- Python version: 3.13

**Running Locally:**

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

**Tools:**

- **Prettier**: Automatic code formatter (80 char print width, prose wrap)
- **ESLint**: Static analysis for bugs and style issues

**Configuration:**

- Prettier: `.prettierrc` (print width 80, prose wrap always)
- ESLint: `frontend/mission-planner/.eslintrc.json`
- Node version: 18.17.1

**Running Locally:**

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

**Tools:**

- **Prettier**: Markdown formatting (80 char print width, prose wrap)
- **Markdownlint-cli2**: Markdown linting (style and consistency checks)

**Configuration:**

- Prettier: `.prettierrc` (shared config)
- Markdownlint: `.markdownlint.jsonc` (if present) or defaults

**Running Locally:**

```bash
# Format with Prettier
npx prettier --write "docs/**/*.md"

# Lint with Markdownlint
markdownlint-cli2 "docs/**/*.md"
```

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

[Back to Contributing](../../CONTRIBUTING.md)
