# Linting Configuration Requirements

**Feature**: 001-codebase-cleanup **Created**: 2025-12-02 **Version**: 1.0

## Overview

This document specifies the exact linting and formatting tool configurations
required to enforce code quality standards during the codebase cleanup
refactoring. These requirements implement **FR-024 through FR-031** from
`spec.md`.

---

## 1. Black Configuration (Python)

**Requirement**: FR-024 - All Python code MUST pass Black formatting (line
length 88)

### Configuration File

**Location**: `pyproject.toml` (project root)

**Required Settings**:

```toml
[tool.black]
line-length = 88
target-version = ['py313']
include = '\.pyi?$'
extend-exclude = '''
/(
  # Excluded directories
    \.eggs
  | \.git
  | \.venv
  | _build
  | build
  | dist
  | migrations
  | node_modules
)/
'''
```

### Execution Contract

**CLI Command**:

```bash
black --check --diff backend/starlink-location/app/
```

**Expected Behavior**:

- Exit code 0: All files compliant
- Exit code 1: Formatting violations detected
- Output: Diff of required changes (if any)

**CI Integration**:

- **Trigger**: On every PR to `001-codebase-cleanup` branch
- **Blocking**: PR merge MUST be blocked if exit code != 0
- **Runs on**: All `.py` files in `backend/starlink-location/app/` (excluding
  `.venv`, `migrations/`)

### Validation Criteria

- Line length MUST NOT exceed 88 characters
- String quotes: Double quotes preferred by Black's defaults
- Indentation: 4 spaces (Python standard)
- Trailing commas: Added automatically by Black
- No inline `# fmt: skip` or `# fmt: off` comments allowed (per FR-029, FR-030)

---

## 2. Prettier Configuration (TypeScript/JavaScript/Markdown)

**Requirement**: FR-025 - All TypeScript/JavaScript code MUST pass Prettier
formatting (print width 80, prose wrap always) **Requirement**: FR-028 - All
Markdown MUST pass Prettier formatting (prose wrap always)

### Configuration File

**Location**: `.prettierrc` (project root)

**Required Settings**:

```json
{
  "printWidth": 80,
  "tabWidth": 2,
  "useTabs": false,
  "semi": true,
  "singleQuote": false,
  "quoteProps": "as-needed",
  "trailingComma": "es5",
  "bracketSpacing": true,
  "arrowParens": "always",
  "proseWrap": "always",
  "endOfLine": "auto",
  "overrides": [
    {
      "files": "*.md",
      "options": {
        "proseWrap": "always"
      }
    }
  ]
}
```

**Location**: `.prettierignore` (project root)

**Required Exclusions**:

```text
# Dependencies
node_modules/
.venv/
dist/
build/

# Auto-generated
package-lock.json
*.min.js

# Data files
/data/
```

### Execution Contract

**CLI Commands**:

```bash
# TypeScript/JavaScript
prettier --check "frontend/mission-planner/src/**/*.{ts,tsx,js,jsx}"

# Markdown
prettier --check "docs/**/*.md" "*.md"
```

**Expected Behavior**:

- Exit code 0: All files compliant
- Exit code 1: Formatting violations detected
- Output: List of non-compliant files

**CI Integration**:

- **Trigger**: On every PR to `001-codebase-cleanup` branch
- **Blocking**: PR merge MUST be blocked if exit code != 0
- **Runs on**:
  - All `.ts`, `.tsx`, `.js`, `.jsx` files in `frontend/mission-planner/src/`
  - All `.md` files in `docs/` and project root

### Validation Criteria

- Print width: 80 characters for code, enforced prose wrap for Markdown
- Indentation: 2 spaces for TS/JS/JSON/YAML
- Semicolons: Required
- Quotes: Double quotes
- Trailing commas: ES5-compatible (objects/arrays, not functions)
- Arrow functions: Always use parentheses around parameters
- No inline `// prettier-ignore` comments allowed (per FR-029, FR-030)

---

## 3. ESLint Configuration (TypeScript/JavaScript)

**Requirement**: FR-026 - All TypeScript/JavaScript code MUST pass ESLint
validation

### Configuration File

**Location**: `frontend/mission-planner/.eslintrc.json` (or project root if
shared)

**Required Settings**:

```json
{
  "env": {
    "browser": true,
    "es2021": true
  },
  "extends": [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react/recommended",
    "plugin:react-hooks/recommended"
  ],
  "parser": "@typescript-eslint/parser",
  "parserOptions": {
    "ecmaVersion": "latest",
    "sourceType": "module",
    "ecmaFeatures": {
      "jsx": true
    }
  },
  "plugins": ["@typescript-eslint", "react", "react-hooks"],
  "rules": {
    "@typescript-eslint/no-explicit-any": "error",
    "@typescript-eslint/explicit-function-return-type": "warn",
    "@typescript-eslint/no-unused-vars": [
      "error",
      { "argsIgnorePattern": "^_" }
    ],
    "react/react-in-jsx-scope": "off",
    "react/prop-types": "off",
    "no-console": ["warn", { "allow": ["warn", "error"] }],
    "prefer-const": "error",
    "no-var": "error"
  },
  "settings": {
    "react": {
      "version": "detect"
    }
  }
}
```

**Location**: `frontend/mission-planner/.eslintignore`

**Required Exclusions**:

```text
node_modules/
dist/
build/
*.config.js
*.config.ts
```

### Execution Contract

**CLI Command**:

```bash
eslint "frontend/mission-planner/src/**/*.{ts,tsx,js,jsx}"
```

**Expected Behavior**:

- Exit code 0: No violations
- Exit code 1: Violations detected
- Output: List of violations with file, line, column, rule ID

**CI Integration**:

- **Trigger**: On every PR to `001-codebase-cleanup` branch
- **Blocking**: PR merge MUST be blocked if exit code != 0
- **Runs on**: All `.ts`, `.tsx`, `.js`, `.jsx` files in
  `frontend/mission-planner/src/`

### Validation Criteria

- **FR-008**: No `any` type usage (enforced by
  `@typescript-eslint/no-explicit-any: error`)
- **FR-009**: Unused variables are errors (enforced by
  `@typescript-eslint/no-unused-vars`)
- **FR-023**: Prefer `const` over `let` where possible (enforced by
  `prefer-const`)
- No inline `// eslint-disable` or `// eslint-disable-next-line` comments
  allowed (per FR-029, FR-030)
- Exception: If rule suppression is absolutely necessary, it MUST be documented
  in PR description and approved by reviewer

---

## 4. markdownlint-cli2 Configuration (Markdown)

**Requirement**: FR-027 - All Markdown MUST pass markdownlint-cli2 validation

### Configuration File

**Location**: `.markdownlint-cli2.jsonc` (project root)

**Required Settings**:

```jsonc
{
  "config": {
    // Default configuration
    "default": true,
    // Specific rule overrides
    "MD013": {
      // Line length - allow long lines (Prettier handles prose wrap)
      "line_length": 200,
      "code_blocks": false,
      "tables": false,
    },
    "MD033": false, // Allow inline HTML (needed for technical docs)
    "MD041": false, // First line doesn't need to be H1 (allow front matter)
  },
  "globs": ["docs/**/*.md", "*.md", "specs/**/*.md"],
  "ignores": [
    "node_modules/**",
    ### /node_modules/
    ".venv/**",
    "data/**",
    "dev/archive/**",
  ],
}
```

### Execution Contract

**CLI Command**:

```bash
markdownlint-cli2 "docs/**/*.md" "*.md" "specs/**/*.md"
```

**Expected Behavior**:

- Exit code 0: No violations
- Exit code 1: Violations detected
- Output: List of violations with file, line, rule ID, description

**CI Integration**:

- **Trigger**: On every PR to `001-codebase-cleanup` branch
- **Blocking**: PR merge MUST be blocked if exit code != 0
- **Runs on**: All `.md` files in `docs/`, `specs/`, and project root

### Validation Criteria

- Headings must follow ATX style (`#`, `##`, not underlines)
- No trailing spaces
- Lists must be consistently formatted
- Code blocks must specify language
- No duplicate heading text (when headings create anchors)
- No inline `<!-- markdownlint-disable -->` comments allowed (per FR-029,
  FR-030)

---

## 5. CI/CD Pipeline Contract

**Requirement**: FR-031 - CI/CD pipeline MUST run all linters on each PR and
block merge if violations detected

### Pipeline Definition

**Location**: `.github/workflows/lint-and-format.yml` (or equivalent CI config)

**Required Workflow**:

```yaml
name: Lint and Format Check

on:
  pull_request:
    branches:
      - 001-codebase-cleanup
      - main
    paths:
      - "backend/starlink-location/app/**/*.py"
      - "frontend/mission-planner/src/**/*.{ts,tsx,js,jsx}"
      - "docs/**/*.md"
      - "*.md"

jobs:
  lint-python:
    name: Check Python with Black
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - name: Install Black
        run: pip install black==24.4.2
      - name: Run Black
        run: black --check --diff backend/starlink-location/app/

  lint-typescript:
    name: Check TypeScript/JavaScript with Prettier and ESLint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - name: Install dependencies
        working-directory: frontend/mission-planner
        run: npm ci
      - name: Run Prettier
        working-directory: frontend/mission-planner
        run: npx prettier --check "src/**/*.{ts,tsx,js,jsx}"
      - name: Run ESLint
        working-directory: frontend/mission-planner
        run: npx eslint "src/**/*.{ts,tsx,js,jsx}"

  lint-markdown:
    name: Check Markdown with Prettier and markdownlint-cli2
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - name: Install Prettier
        run: npm install -g prettier@3.2.5
      - name: Run Prettier on Markdown
        run: prettier --check "docs/**/*.md" "*.md" "specs/**/*.md"
      - name: Install markdownlint-cli2
        run: npm install -g markdownlint-cli2@0.12.1
      - name: Run markdownlint-cli2
        run: markdownlint-cli2 "docs/**/*.md" "*.md" "specs/**/*.md"
```

### Pipeline Execution Contract

**Trigger Conditions**:

- MUST run on every PR created against `001-codebase-cleanup` or `main` branches
- MUST run on every push to an open PR (including force pushes)
- SHOULD complete within 5 minutes

**Blocking Behavior**:

- **Required Status Checks**: All jobs (`lint-python`, `lint-typescript`,
  `lint-markdown`) MUST pass
- **Merge Prevention**: GitHub branch protection MUST enforce that all required
  checks pass before merge
- **Failure Reporting**: Failed checks MUST show exact violations in PR comments
  or check details

**Configuration in GitHub**:

1. Navigate to repository Settings > Branches > Branch protection rules
2. Add rule for `001-codebase-cleanup` branch
3. Enable "Require status checks to pass before merging"
4. Select all lint jobs as required checks
5. Enable "Require branches to be up to date before merging"

### Error Handling

**If CI fails**:

1. PR author is notified via GitHub comment with violation details
2. PR cannot be merged until violations are fixed
3. Author must either:
   - Fix violations and push updates (triggers CI re-run)
   - Document why violation is acceptable and request reviewer override (RARE -
     requires strong justification per FR-030)

**CI Infrastructure Failures** (e.g., GitHub Actions downtime):

- If CI system is unavailable, manual verification is required:
  - Reviewer MUST run linters locally before approval
  - Reviewer MUST document manual verification in approval comment

---

## 6. Tool Version Requirements

To ensure consistency across development and CI environments, the following tool
versions MUST be used:

| Tool              | Version  | Install Command                           |
| ----------------- | -------- | ----------------------------------------- |
| Black             | 24.4.2   | `pip install black==24.4.2`               |
| Prettier          | 3.2.5    | `npm install -g prettier@3.2.5`           |
| ESLint            | 8.57.0   | `npm install eslint@8.57.0`               |
| markdownlint-cli2 | 0.12.1   | `npm install -g markdownlint-cli2@0.12.1` |
| Python            | 3.13     | (system Python or via pyenv)              |
| Node.js           | 20.x LTS | (via nvm or system package manager)       |

**Version Pinning Strategy**:

- Python: Pin in `requirements-dev.txt` or `pyproject.toml`
  `[tool.poetry.dev-dependencies]`
- Node.js: Pin in `frontend/mission-planner/package.json` `devDependencies`
- CI: Pin explicitly in workflow YAML files

---

## 7. Local Development Workflow

Developers MUST run linters locally before pushing changes:

### Pre-commit Hook (Recommended)

**Location**: `.pre-commit-config.yaml` (project root)

**Configuration**:

```yaml
repos:
  - repo: <https://github.com/psf/black>
    rev: 24.4.2
    hooks:
      - id: black
        language_version: python3.13
        files: ^backend/starlink-location/app/.*\.py$

  - repo: <https://github.com/pre-commit/mirrors-prettier>
    rev: v3.2.5
    hooks:
      - id: prettier
        types_or: [typescript, tsx, javascript, jsx, markdown]
        files: ^(frontend/mission-planner/src/.*\.(ts|tsx|js|jsx)|docs/.*\.md|.*\.md)$

  - repo: <https://github.com/pre-commit/mirrors-eslint>
    rev: v8.57.0
    hooks:
      - id: eslint
        files: ^frontend/mission-planner/src/.*\.(ts|tsx|js|jsx)$
        additional_dependencies:
          - eslint@8.57.0
          - "@typescript-eslint/parser@7.0.0"
          - "@typescript-eslint/eslint-plugin@7.0.0"

  - repo: <https://github.com/DavidAnson/markdownlint-cli2>
    rev: v0.12.1
    hooks:
      - id: markdownlint-cli2
        files: ^(docs/.*\.md|.*\.md|specs/.*\.md)$
```

**Setup**:

```bash
# Install pre-commit
pip install pre-commit==3.6.0

# Install hooks
pre-commit install

# Test hooks
pre-commit run --all-files
```

### Manual Linting Commands

If not using pre-commit, developers MUST run these commands before creating a
PR:

```bash
# Python
black --check backend/starlink-location/app/
# (Fix with: black backend/starlink-location/app/)

# TypeScript/JavaScript
cd frontend/mission-planner
npx prettier --check "src/**/*.{ts,tsx,js,jsx}"
# (Fix with: npx prettier --write "src/**/*.{ts,tsx,js,jsx}")
npx eslint "src/**/*.{ts,tsx,js,jsx}"
# (Fix with: npx eslint --fix "src/**/*.{ts,tsx,js,jsx}")

# Markdown
prettier --check "docs/**/*.md" "*.md" "specs/**/*.md"
# (Fix with: prettier --write "docs/**/*.md" "*.md" "specs/**/*.md")
markdownlint-cli2 "docs/**/*.md" "*.md" "specs/**/*.md"
# (Fix with: markdownlint-cli2 --fix "docs/**/*.md" "*.md" "specs/**/*.md")
```

---

## 8. Validation Checklist for PRs

Before approving a PR, reviewers MUST verify:

- [ ] All CI lint jobs passed (green checkmarks on PR)
- [ ] No `# fmt: skip`, `// prettier-ignore`, `// eslint-disable`, or
      `<!-- markdownlint-disable -->` comments added (scan PR diff manually)
- [ ] If lint suppressions exist, PR description documents justification and
      reviewer approved the exception
- [ ] Local manual lint check confirms CI results (if CI failed to run)

---

## 9. Exception Process

**When lint rule violations cannot be fixed** (RARE):

1. **Document in PR**: Author MUST add detailed explanation in PR description:
   - Which rule is violated
   - Why fixing it is not feasible (technical reason)
   - What alternative approach was considered
   - Risk assessment if rule is ignored
2. **Reviewer Approval**: Requires explicit approval from reviewer with comment
   acknowledging exception
3. **Follow-up Issue**: Create GitHub issue to track technical debt and revisit
   in future
4. **FR-004 Justification**: If file remains oversized due to exception, add
   FR-004 comment per spec

---

## 10. Troubleshooting

### Black fails with "reformatted" error

**Cause**: File not formatted according to Black's rules

**Solution**:

```bash
black backend/starlink-location/app/filename.py
```

### Prettier reports "Code style issues found"

**Cause**: File not formatted according to Prettier's rules

**Solution**:

```bash
prettier --write filename.ts
```

### ESLint reports "@typescript-eslint/no-explicit-any" error

**Cause**: Usage of `any` type (violates FR-008)

**Solution**: Replace `any` with specific type annotation or `unknown` (if type
truly indeterminate)

### markdownlint reports "MD013/line-length"

**Cause**: Line exceeds configured length (200 chars)

**Solution**: Run Prettier to auto-wrap prose (`prettier --write filename.md`)

### CI passes locally but fails in GitHub Actions

**Cause**: Version mismatch or file not committed

**Solution**:

- Check tool versions match CI (`black --version`, `prettier --version`, etc.)
- Ensure `.prettierrc`, `.eslintrc.json`, `.markdownlint-cli2.jsonc` are
  committed

---

## 11. Related Requirements

This document implements the following requirements from `spec.md`:

- **FR-024**: Black formatting with line length 88
- **FR-025**: Prettier formatting for TS/JS (print width 80, prose wrap always)
- **FR-026**: ESLint validation for TS/JS
- **FR-027**: markdownlint-cli2 validation for Markdown
- **FR-028**: Prettier formatting for Markdown (prose wrap always)
- **FR-029**: No inline lint-disable comments
- **FR-030**: All linting violations fixed, not suppressed
- **FR-031**: CI/CD pipeline runs all linters and blocks merge on violations

**Success Criteria**:

- **SC-006**: 0 files contain inline lint-disable comments in refactored code

---

**Document Version**: 1.0 **Last Updated**: 2025-12-02 **Maintained By**: Claude
Code Agent
