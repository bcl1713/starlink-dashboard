# Contributing to Starlink Dashboard

This guide outlines the development workflow, code quality standards, and
linting setup for the Starlink Dashboard project.

---

## Quick Links

- [Code Quality Standards](./contributing/code-quality.md) - Linting and
  formatting
- [Development Workflow](./contributing/development-workflow.md) - Branch, PR,
  and CI/CD
- [Testing Guide](./contributing/testing-guide.md) - Running tests and PR
  guidelines
- [Troubleshooting](./contributing/troubleshooting.md) - Common issues

---

## Quick Start

### 1. Install Pre-commit Hooks

```bash
pip install pre-commit
pre-commit install
```

### 2. Create Feature Branch

```bash
git checkout -b feat/your-feature-name
```

### 3. Make Changes and Commit

```bash
git add .
git commit -m "feat: description of changes"
```

Pre-commit hooks will automatically run linting and formatting.

### 4. Push and Create PR

```bash
git push origin feat/your-feature-name
```

Create a pull request on GitHub. CI/CD will verify all checks pass.

---

## Code Quality Tools

### Python

- **Black**: Code formatting (88 char line length)
- **Ruff**: Linting (syntax, security, style)

### JavaScript/TypeScript

- **Prettier**: Code formatting (80 char print width)
- **ESLint**: Static analysis

### Markdown

- **Prettier**: Formatting (80 char print width, prose wrap)
- **Markdownlint**: Style consistency

**See:** [Code Quality Standards](./contributing/code-quality.md) for detailed
configuration and usage.

---

## Development Workflow

1. Create feature branch from main
2. Make code changes
3. Commit (pre-commit hooks run automatically)
4. Push and create PR
5. CI/CD verifies all checks pass
6. Code review and merge

**See:** [Development Workflow](./contributing/development-workflow.md) for
complete workflow details.

---

## Testing

### Python Tests

```bash
cd backend/starlink-location
pytest --cov=app tests/
```

### JavaScript Tests

```bash
cd frontend/mission-planner
npm test -- --coverage
```

**See:** [Testing Guide](./contributing/testing-guide.md) for test requirements
and PR guidelines.

---

## Code Style Guidelines

### File Size Limits

- **Target**: 300 lines per file
- **Python**: 70%+ compliance (80/113 files)
- **TypeScript**: 100% compliance (52/52 files)
- **Markdown**: 100% compliance (60+ files)

### Line Length

- **Python**: 88 characters (Black default)
- **JavaScript/TypeScript**: 80 characters
- **Markdown**: 80 characters with prose wrap

**See:**
[Code Quality Standards](./contributing/code-quality.md#code-style-guidelines)
for complete style guidelines.

---

## Common Commands

### Format All Code

```bash
# Python
black backend/starlink-location/app

# JavaScript/TypeScript
cd frontend/mission-planner && npx prettier --write "src/**/*.{ts,tsx,js,jsx}"

# Markdown
npx prettier --write "docs/**/*.md"
```

### Check Linting

```bash
# Python
black --check backend/starlink-location/app
ruff check backend/starlink-location/app

# JavaScript/TypeScript
cd frontend/mission-planner && npx eslint src

# Markdown
markdownlint-cli2 "docs/**/*.md"
```

---

## Getting Help

- **Setup Issues**: See [Troubleshooting](./contributing/troubleshooting.md)
- **Code Standards**: See [Code Quality](./contributing/code-quality.md)
- **Workflow**: See
  [Development Workflow](./contributing/development-workflow.md)
- **Testing**: See [Testing Guide](./contributing/testing-guide.md)

---

## Related Documentation

- [Development Status](../dev/STATUS.md) - Current development status
- [Architecture](./design-document.md) - System architecture
- [Setup Guide](./SETUP-GUIDE.md) - Development environment setup

---

[Back to README](../README.md)
