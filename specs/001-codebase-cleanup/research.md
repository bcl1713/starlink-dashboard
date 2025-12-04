# Codebase Cleanup Initiative: Research & Best Practices

**Document Status:** Research Complete **Created:** 2025-12-02 **Last Updated:**
2025-12-02 **Project:** Starlink Dashboard

---

## Executive Summary

This document outlines research findings and best practices for the codebase
cleanup initiative. The primary goals are to improve code maintainability,
establish consistent formatting standards, and reduce technical debt through
systematic refactoring.

**Current State Analysis:**

- **Python Backend:** 1,047 lines in routes.py, 1,093 lines in pois.py
  (monolithic API modules)
- **React Frontend:** 611 total lines in large component files (MissionDetail,
  LegDetail pages)
- **Documentation:** 9,878 total lines across 20 markdown files (some files
  exceed 1,000 lines)
- **Existing Tooling:** Prettier configured (.prettierrc present), ESLint in
  frontend, no Black/ruff configuration detected in backend

**Key Recommendations:**

1. **Incremental refactoring** over big-bang rewrites
2. **Route-based decomposition** for FastAPI endpoints
3. **Custom hook extraction** for React component logic
4. **Sub-document strategy** for large markdown files
5. **Pre-commit hooks** for automated linting/formatting

---

## 1. Python Module Decomposition Strategies

### Decision: Route-Based Decomposition with Service Layer Extraction

We will decompose large FastAPI route files by grouping related endpoints into
separate modules, extracting shared business logic into dedicated service
modules, and maintaining backward compatibility through careful import

### Python: Implementation Notes

**Target Structure for `/api/routes`:**

```text
app/api/routes/
├── __init__.py           # Re-export routers for backward compatibility
├── management.py         # List, get, activate, deactivate routes
├── upload.py             # Upload, download, delete routes
├── stats.py              # Stats, progress, ETA calculations
├── timing.py             # Route timing profile endpoints
└── cache.py              # ETA cache management endpoints
```

**Target Structure for `/api/pois`:**

```text
app/api/pois/
├── __init__.py           # Re-export routers
├── crud.py               # Create, read, update, delete POIs
├── etas.py               # ETA calculations and list with ETAs
├── stats.py              # Next destination, approaching POIs
└── projections.py        # POI projection calculations (may be service)
```

**Migration Steps:**

1. **Create new module structure** (e.g., `app/api/routes/management.py`)
2. **Copy endpoints** to new files with router prefixes
3. **Extract shared logic** into service layer (e.g.,
   `app/services/route_stats.py`)
4. **Update imports** in `__init__.py` to re-export all routers
5. **Run tests** to verify no regressions
6. **Update main.py** to include all sub-routers
7. **Remove old monolithic file** once all tests pass

**Maintaining Import Compatibility:**

```python
# app/api/routes/__init__.py (example)
from app.api.routes.management import router as management_router
from app.api.routes.upload import router as upload_router
from app.api.routes.stats import router as stats_router
from app.api.routes.timing import router as timing_router
from app.api.routes.cache import router as cache_router

# Create a main router that includes all sub-routers
from fastapi import APIRouter

router = APIRouter(prefix="/api/routes", tags=["routes"])
router.include_router(management_router)
router.include_router(upload_router)
router.include_router(stats_router)
router.include_router(timing_router)
router.include_router(cache_router)
```

**Service Layer Extraction:**

When multiple endpoints share complex logic (e.g., ETA calculations, bearing
computations), extract into services:

```python
# Before (in pois.py)
def calculate_bearing(lat1, lon1, lat2, lon2):
    # 25 lines of math...
    pass

# After
# app/services/navigation.py
class NavigationService:
    def calculate_bearing(self, lat1, lon1, lat2, lon2):
        # 25 lines of math...
        pass

    def calculate_course_status(self, heading, bearing):
        # ...
        pass
```

**Testing Strategy:**

- Run **all existing integration tests** after each refactoring step
- Add **endpoint smoke tests** if coverage gaps exist
- Use **pytest fixtures** to test new service modules in isolation

---

## 2. TypeScript/React Component Refactoring

### Decision: Custom Hook Extraction + Component Composition

We will decompose large React components (400+ lines) by extracting state
management and side effects into custom hooks, splitting UI sections into
smaller sub-components, and using component composition patterns.

### React: Rationale

1. **React Best Practices:** The React documentation emphasizes "composition
   over inheritance" and encourages extracting logic into custom hooks for
   reusability and testability.

1. **Cognitive Load:** Components exceeding 300 lines become difficult to
   understand and modify. Splitting into focused sub-components improves
   developer experience.

1. **Reusability:** Custom hooks can be shared across multiple components,
   reducing code duplication.

1. **Testing:** Smaller components and isolated hooks are easier to unit test.

### React: Alternatives Considered

| Approach                            | Pros                       | Cons                                          |
| ----------------------------------- | -------------------------- | --------------------------------------------- |
| Keep monolithic components          | No refactoring effort      | Difficult to maintain and test                |
| Full component rewrite              | Clean slate                | High risk, breaks existing functionality      |
| State management library            | Centralized state          | Overkill for current complexity               |
| Custom hooks + composition (CHOSEN) | Balances risk and progress | Requires discipline to avoid over-abstraction |

### React: Implementation Notes

**Target Structure for Large Components:**

```text
MissionDetailPage.tsx (400+ lines)
↓
MissionDetailPage.tsx (150 lines)          # Main component, layout
├── useMissionData.ts                      # Data fetching hook
├── useMissionActions.ts                   # Action handlers hook
├── MissionHeader.tsx                      # Header section
├── MissionLegsTable.tsx                   # Legs table
└── MissionMetadata.tsx                    # Metadata sidebar
```

**Custom Hook Extraction Pattern:**

```typescript
// Before (in MissionDetailPage.tsx)
const MissionDetailPage = () => {
  const [mission, setMission] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMission(id).then(setMission).finally(() => setLoading(false));
  }, [id]);

  // ... 300 more lines
}

// After
// hooks/useMissionData.ts
export const useMissionData = (missionId: string) => {
  const [mission, setMission] = useState<Mission | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    setLoading(true);
    fetchMission(missionId)
      .then(setMission)
      .catch(setError)
      .finally(() => setLoading(false));
  }, [missionId]);

  return { mission, loading, error };
}

// MissionDetailPage.tsx
const MissionDetailPage = () => {
  const { id } = useParams();
  const { mission, loading, error } = useMissionData(id);

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorMessage error={error} />;

  return (
    <div>
      <MissionHeader mission={mission} />
      <MissionLegsTable legs={mission.legs} />
      <MissionMetadata mission={mission} />
    </div>
  );
}
```

**Component Composition Guidelines:**

1. **Single Responsibility:** Each component should have one clear purpose
2. **Props Over State:** Pass data down via props rather than duplicating state
3. **Container/Presentational Split:** Separate data-fetching (containers) from
   UI rendering (presentational)
4. **Avoid Prop Drilling:** Use context or composition for deeply nested props

**Refactoring Checklist:**

- [ ] Extract data fetching into custom hooks
- [ ] Extract action handlers (onClick, onSubmit) into custom hooks
- [ ] Split render logic into sub-components (header, body, footer)
- [ ] Move inline styles/classes to separate style files (if large)
- [ ] Add PropTypes or TypeScript interfaces for all components
- [ ] Update tests to cover new hooks and components

---

## 3. Documentation Organization

### Decision: Sub-Document Strategy with Navigation Index

We will split large markdown files (1,000+ lines) into focused sub-documents
organized by topic, maintain a centralized index with clear navigation, and use
relative paths for internal linking.

### Docs: Rationale

1. **Cognitive Load:** Documents exceeding 500 lines are difficult to navigate,
   even with a table of contents. Readers often miss important sections.

1. **Maintenance:** Smaller documents are easier to update without introducing
   inconsistencies or merge conflicts.

1. **Discoverability:** A well-structured index improves documentation
   discoverability for new team members.

1. **Version Control:** Smaller files produce cleaner git diffs and make it
   easier to track changes over time.

### Docs: Alternatives Considered

| Approach                         | Pros                                   | Cons                                        |
| -------------------------------- | -------------------------------------- | ------------------------------------------- |
| Single large markdown file       | Simple navigation (Ctrl+F)             | Overwhelming, hard to maintain              |
| Wiki/separate platform           | Better search, versioning              | Disconnected from codebase, sync issues     |
| Docusaurus/MkDocs                | Professional documentation site        | Overkill for current needs, adds complexity |
| **Sub-docs with index (CHOSEN)** | **Balances structure with simplicity** | **Requires consistent linking discipline**  |

### Docs: Implementation Notes

**Current Documentation Structure:**

```text
docs/
├── INDEX.md                               # 20 files, ~10K lines total
├── design-document.md                     # Large, general architecture
├── phased-development-plan.md
├── ROUTE-TIMING-GUIDE.md
├── API-REFERENCE.md
└── ... (17 more files)
```

**Proposed Reorganized Structure:**

```text
docs/
├── README.md                              # Project overview + quick start
├── INDEX.md                               # Master index with all docs
├── getting-started/
│   ├── setup.md                          # Setup guide
│   ├── quick-start.md                    # 5-minute tutorial
│   └── troubleshooting.md                # Common issues
├── architecture/
│   ├── overview.md                       # System architecture
│   ├── backend.md                        # Backend components
│   ├── frontend.md                       # Frontend architecture
│   └── data-flow.md                      # Data flow diagrams
├── api/
│   ├── routes.md                         # Routes API endpoints
│   ├── pois.md                           # POIs API endpoints
│   ├── missions.md                       # Missions API endpoints
│   └── flight-status.md                  # Flight status API
├── features/
│   ├── route-management.md               # Route management guide
│   ├── poi-system.md                     # POI system guide
│   ├── mission-planning.md               # Mission planning guide
│   ├── eta-timing.md                     # ETA and timing features
│   └── satellite-tracking.md             # Satellite tracking
├── operations/
│   ├── deployment.md                     # Deployment guide
│   ├── monitoring.md                     # Monitoring setup
│   └── performance.md                    # Performance tuning
└── development/
    ├── contributing.md                   # Contribution guidelines
    ├── testing.md                        # Testing strategy
    ├── workflows.md                      # Development workflows
    └── naming-conventions.md             # Code style guide
```

**Documentation Linking Strategies:**

**Relative vs. Absolute Paths:**

- **Use relative paths** for internal documentation links
- **Benefit:** Links work in GitHub, local editors, and static site generators
- **Example:** `[API Reference](../api/routes.md)` instead of
  `/docs/api/routes.md`

**Table of Contents Generation:**

1. **Manual TOC:** For documents < 200 lines, manually maintain TOC
2. **Auto-generated TOC:** For documents 200-500 lines, use `markdown-toc` or
   similar tools
3. **Sub-document split:** For documents > 500 lines, split into multiple files
   rather than generating complex TOC

#### Example: Splitting a Large Document

```markdown
# Before: design-document.md (1,500 lines)

## 1. Introduction

## 2. Architecture

### 2.1 Backend

### 2.2 Frontend

### 2.3 Database

## 3. API Endpoints

### 3.1 Routes API

### 3.2 POIs API

## 4. Deployment

## 5. Monitoring

# After: Split into focused documents

## docs/README.md (overview + quick start)

## docs/architecture/overview.md (introduction + high-level)

## docs/architecture/backend.md (section 2.1)

## docs/architecture/frontend.md (section 2.2)

## docs/architecture/database.md (section 2.3)

## docs/api/routes.md (section 3.1)

## docs/api/pois.md (section 3.2)

## docs/operations/deployment.md (section 4)

## docs/operations/monitoring.md (section 5)
```

**Cross-Reference Best Practices:**

```markdown
<!-- Good: Descriptive link text with context -->

For detailed API specifications, see the
[Routes API documentation](../api/routes.md).

<!-- Bad: Generic link text -->

For more information, click [here](../api/routes.md).

<!-- Good: Deep link to specific section -->

Review the
[ETA calculation algorithm](../features/eta-timing.md#calculation-algorithm).
```

**Migration Strategy:**

1. **Create new directory structure** (getting-started/, architecture/, etc.)
2. **Copy sections** from large files to new focused documents
3. **Update INDEX.md** with new structure and links
4. **Add "See also" sections** for related documents
5. **Update all cross-references** to use new paths
6. **Archive old files** (move to `docs/archive/`) rather than deleting
7. **Add redirects** in README if possible (GitHub supports this)

---

## 4. Safe Refactoring Workflow

### Decision: Incremental Refactoring with Test-First Verification

We will adopt an incremental refactoring approach that prioritizes small,
isolated changes with comprehensive test coverage before and after each
refactoring step. Use feature branches with focused PRs and never refactor
without a safety net of passing tests.

### Safe Refactor: Rationale

1. **Risk Mitigation:** Large refactoring efforts often introduce subtle bugs
   that are difficult to trace. Incremental changes limit the blast radius.

1. **Continuous Integration:** Smaller changes integrate more easily, reducing
   merge conflicts and enabling faster code reviews.

1. **Rollback Safety:** If a refactoring introduces issues, it's easier to
   revert a small change than to unwind a massive rewrite.

1. **Team Confidence:** Developers are more likely to approve and merge small,
   well-tested refactorings than large, risky changes.

### Safe Refactor: Alternatives Considered

| Approach                         | Pros                           | Cons                                   |
| -------------------------------- | ------------------------------ | -------------------------------------- |
| Big-bang rewrite                 | Clean slate, modern patterns   | High risk, long integration time       |
| No refactoring                   | No risk                        | Technical debt accumulates             |
| Opportunistic refactoring        | Low overhead                   | Inconsistent, may never complete       |
| **Incremental + tests (CHOSEN)** | **Balances risk and progress** | **Requires discipline and automation** |

### Safe Refactor: Implementation Notes

**Incremental Refactoring Techniques:**

1. **Extract Method/Function**
   - Move complex logic into named functions
   - Improves readability without changing behavior
   - Low risk, high value

2. **Extract Class/Module**
   - Group related functions into cohesive modules
   - Reduces coupling between components
   - Medium risk, high value

3. **Rename Variables/Functions**
   - Clarify intent with descriptive names
   - Use IDE refactoring tools for safety
   - Very low risk, medium value

4. **Introduce Parameter Object**
   - Replace long parameter lists with objects
   - Improves function signatures
   - Low risk, medium value

5. **Replace Conditional with Polymorphism**
   - Use strategy pattern for complex branching
   - Only for frequently changing logic
   - Medium risk, medium value

**Refactoring Workflow:**

```text
┌─────────────────────────────────────────────────────────────┐
│ 1. IDENTIFY REFACTORING TARGET                              │
│    - Code smell: long functions, duplicated logic, etc.     │
│    - Choose smallest possible refactoring unit              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. ENSURE TEST COVERAGE                                     │
│    - Run existing tests → All passing                       │
│    - Add tests if coverage < 80%                            │
│    - Document expected behavior                             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. CREATE FEATURE BRANCH                                    │
│    git checkout -b refactor/descriptive-name                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. REFACTOR (Behavior-Preserving Changes ONLY)              │
│    - Extract function/class                                 │
│    - Rename for clarity                                     │
│    - Move to appropriate module                             │
│    - DO NOT add features or fix bugs in same commit         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. RUN TESTS CONTINUOUSLY                                   │
│    - pytest backend/tests (after each Python change)        │
│    - npm test (after each TypeScript change)                │
│    - Fix immediately if tests fail                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. COMMIT WITH DESCRIPTIVE MESSAGE                          │
│    git commit -m "refactor: extract POI ETA calculation"    │
│    - Use conventional commits format                        │
│    - Reference issue/task if applicable                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 7. CREATE PULL REQUEST                                      │
│    - Title: "refactor: [scope] brief description"           │
│    - Description: What was refactored and why               │
│    - Link to related issues                                 │
│    - Request review from 1-2 team members                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 8. CODE REVIEW                                              │
│    - Verify tests pass in CI                                │
│    - Check no behavior changes                              │
│    - Approve if code is clearer and tests pass              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 9. MERGE TO MAIN                                            │
│    - Use squash merge for clean history                     │
│    - Delete feature branch after merge                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 10. REPEAT                                                  │
│     - Continue with next refactoring target                 │
│     - Aim for 1-2 refactoring PRs per week                  │
└─────────────────────────────────────────────────────────────┘
```

**Testing Strategies for Behavior-Preserving Refactors:**

1. **Characterization Tests (Legacy Code)**
   - Write tests that capture current behavior
   - Even if behavior is buggy, document it
   - Refactor, then fix bugs in separate commits

2. **Integration Tests (API Endpoints)**
   - Test HTTP request/response behavior
   - Verify status codes, response schemas
   - Use test fixtures for consistent data

3. **Unit Tests (Service Layer)**
   - Test isolated business logic
   - Mock external dependencies
   - Aim for 80%+ code coverage

4. **Snapshot Tests (React Components)**
   - Capture component render output
   - Detect unintended UI changes
   - Update snapshots consciously

**Git Workflow for Large-Scale Refactoring:**

```bash
# Branch Strategy
main                    # Always stable, deployable
├── refactor/routes-api # Decompose routes.py (PR #1)
├── refactor/pois-api   # Decompose pois.py (PR #2)
└── refactor/docs       # Reorganize documentation (PR #3)

# PR Sizing Guidelines
- Small: < 200 lines changed (preferred)
- Medium: 200-500 lines changed (acceptable)
- Large: > 500 lines changed (break into smaller PRs)

# Commit Message Format (Conventional Commits)
refactor(routes): extract route statistics endpoints
refactor(pois): move ETA calculations to service layer
docs(api): split API reference into separate files
```

**Rollback Strategy:**

If a refactoring introduces production issues:

1. **Immediate Rollback:** Revert the merge commit on main
2. **Root Cause Analysis:** Identify what broke and why tests didn't catch it
3. **Add Tests:** Write tests that reproduce the issue
4. **Fix Forward:** Create a new PR with the fix and enhanced tests
5. **Post-Mortem:** Document lessons learned

---

## 5. Linting and Formatting Automation

### Decision: Pre-Commit Hooks with CI/CD Integration

We will implement automated linting and formatting using pre-commit hooks for
local development and CI/CD checks for pull requests. Use Black for Python,
Prettier for JavaScript/TypeScript/Markdown, ESLint for JS/TS, and markdownlint
for documentation.

### Linting: Rationale

1. **Consistency:** Automated formatting eliminates style debates and ensures a
   consistent codebase.

1. **Quality Gates:** Pre-commit hooks catch issues before they reach code
   review, reducing review time.

1. **Developer Experience:** Automatic formatting reduces cognitive load,
   allowing developers to focus on logic rather than style.

1. **CI/CD Integration:** Enforcing checks in CI prevents non-compliant code
   from merging.

### Alternatives Considered

| Approach                     | Pros                            | Cons                                    |
| ---------------------------- | ------------------------------- | --------------------------------------- |
| Manual formatting            | No tooling setup required       | Inconsistent style, wasted review time  |
| Editor-only formatting       | Works for individual developers | Not enforced, leads to inconsistency    |
| CI-only checks               | Catches issues eventually       | Slows feedback loop, wastes CI time     |
| **Pre-commit + CI (CHOSEN)** | **Fast feedback + enforcement** | **Requires initial setup and training** |

### Implementation Notes

**Tool Selection:**

| Language/File Type | Linter                        | Formatter | Rationale                         |
| ------------------ | ----------------------------- | --------- | --------------------------------- |
| Python             | ruff (replaces flake8/pylint) | Black     | Fast, modern, PEP 8 compliant     |
| TypeScript/JS      | ESLint                        | Prettier  | Industry standard, extensible     |
| Markdown           | markdownlint                  | Prettier  | Ensures documentation consistency |
| JSON/YAML          | -                             | Prettier  | Consistent configuration files    |
| CSS/SCSS           | Stylelint                     | Prettier  | Enforces best practices           |

**Pre-Commit Hook Setup:**

Install `pre-commit` framework:

```bash
# Install pre-commit (Python package)
pip install pre-commit

# Install hooks from .pre-commit-config.yaml
pre-commit install
```

**`.pre-commit-config.yaml` Configuration:**

```yaml
# .pre-commit-config.yaml
repos:
  # Python formatting and linting
  - repo: <https://github.com/psf/black>
    rev: 24.10.0
    hooks:
      - id: black
        language_version: python3.12
        args: [--line-length=100]

  - repo: <https://github.com/astral-sh/ruff-pre-commit>
    rev: v0.8.0
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]

  # JavaScript/TypeScript/Markdown formatting
  - repo: <https://github.com/pre-commit/mirrors-prettier>
    rev: v4.0.0-alpha.8
    hooks:
      - id: prettier
        types_or: [javascript, jsx, ts, tsx, json, yaml, markdown]
        args: [--config, .prettierrc]

  # Markdown linting
  - repo: <https://github.com/igorshubovych/markdownlint-cli>
    rev: v0.43.0
    hooks:
      - id: markdownlint
        args: [--fix, --config, .markdownlint.json]

  # General file cleanup
  - repo: <https://github.com/pre-commit/pre-commit-hooks>
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-merge-conflict
      - id: check-added-large-files
        args: [--maxkb=500]

  # Python import sorting
  - repo: <https://github.com/pycqa/isort>
    rev: 5.13.2
    hooks:
      - id: isort
        args: [--profile, black]
```

**Black Configuration (Python):**

```toml
# pyproject.toml (create in backend/starlink-location/)
[tool.black]
line-length = 100
target-version = ['py312']
include = '\.pyi?$'
exclude = '''
/(
    \.git
  | \.venv
  | build
  | dist
  | __pycache__
)/
'''
```

**Ruff Configuration (Python Linter):**

```toml
# pyproject.toml (add to same file)
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
]
ignore = [
    "E501",  # line too long (handled by Black)
]

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]  # Allow unused imports in __init__
```

**Prettier Configuration (Already Exists):**

```json
{
  "printWidth": 80,
  "proseWrap": "always",
  "endOfLine": "auto"
}
```

**ESLint Configuration (Frontend):**

```json
// frontend/mission-planner/.eslintrc.json
{
  "extends": [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react/recommended",
    "plugin:react-hooks/recommended",
    "prettier"
  ],
  "parser": "@typescript-eslint/parser",
  "parserOptions": {
    "ecmaVersion": 2022,
    "sourceType": "module",
    "ecmaFeatures": {
      "jsx": true
    }
  },
  "rules": {
    "react/react-in-jsx-scope": "off",
    "@typescript-eslint/no-unused-vars": [
      "warn",
      { "argsIgnorePattern": "^_" }
    ],
    "@typescript-eslint/explicit-module-boundary-types": "off"
  },
  "settings": {
    "react": {
      "version": "detect"
    }
  }
}
```

**Markdownlint Configuration:**

```json
// .markdownlint.json
{
  "default": true,
  "MD013": false,
  "MD033": false,
  "MD041": false
}
```

**CI/CD Integration (GitHub Actions):**

```yaml
# .github/workflows/lint.yml
name: Lint and Format Check

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  lint-python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: |
          pip install black ruff
      - name: Run Black
        run: black --check backend/
      - name: Run Ruff
        run: ruff check backend/

  lint-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - name: Install dependencies
        run: cd frontend/mission-planner && npm ci
      - name: Run ESLint
        run: cd frontend/mission-planner && npm run lint
      - name: Run Prettier
        run: npx prettier --check "frontend/**/*.{ts,tsx,json,md}"

  lint-docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run markdownlint
        run: |
          npm install -g markdownlint-cli
          markdownlint docs/
```

**Handling Linting Violations in Existing Code:**

#### Option 1: Fix All at Once (Recommended for Small Codebases)

```bash
# Format all Python files
black backend/

# Fix all auto-fixable issues
ruff check --fix backend/

# Format all frontend files
cd frontend/mission-planner && npx prettier --write "src/**/*.{ts,tsx}"

# Commit changes
git add .
git commit -m "style: apply automated formatting to entire codebase"
```

#### Option 2: Incremental Fixing (Recommended for Large Codebases)

```yaml
# .pre-commit-config.yaml (temporary configuration)
repos:
  - repo: <https://github.com/psf/black>
    rev: 24.10.0
    hooks:
      - id: black
        # Only format files in git staging area
        stages: [commit]
```

Strategy:

- Enable pre-commit hooks for new changes only
- Create a backlog of "fix formatting" tasks
- Fix one module/directory per PR
- After 4-6 weeks, enable strict checks for all files

**Developer Training:**

1. **Onboarding Document:** Create `docs/development/formatting-guide.md`
2. **Team Meeting:** 15-minute demo of pre-commit hooks
3. **PR Template:** Add checklist item: "[ ] Code is formatted (pre-commit hooks
   passed)"
4. **Grace Period:** Give team 2 weeks to adapt before enforcing CI checks

**Bypassing Hooks (Emergency Only):**

```bash
# Skip pre-commit hooks (use sparingly)
git commit --no-verify -m "emergency fix"

# Note: CI will still catch violations
```

**Common Issues and Solutions:**

| Issue                    | Solution                                       |
| ------------------------ | ---------------------------------------------- |
| Pre-commit hooks slow    | Reduce scope to only changed files             |
| Black and ruff conflict  | Use `--profile black` for isort/ruff           |
| Prettier breaks markdown | Configure `proseWrap: always` in `.prettierrc` |
| ESLint too strict        | Customize rules in `.eslintrc.json`            |

---

## 6. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)

**Deliverables:**

- [ ] Set up Black, Ruff, Prettier, ESLint configurations
- [ ] Create `.pre-commit-config.yaml`
- [ ] Run formatters on entire codebase (create baseline)
- [ ] Set up CI/CD linting checks
- [ ] Document formatting workflow in `docs/development/`

**Success Metrics:**

- All CI checks pass
- Pre-commit hooks installed for all developers
- Zero manual formatting debates in code reviews

### Phase 2: Backend Refactoring (Weeks 3-6)

**Deliverables:**

- [ ] Decompose `app/api/routes.py` into sub-modules
- [ ] Decompose `app/api/pois.py` into sub-modules
- [ ] Extract shared logic into service layer
- [ ] Update integration tests
- [ ] Update API documentation

**Success Metrics:**

- All route files < 300 lines
- Test coverage remains > 80%
- No regressions in API behavior

### Phase 3: Frontend Refactoring (Weeks 7-9)

**Deliverables:**

- [ ] Extract custom hooks from large components
- [ ] Split MissionDetailPage.tsx into sub-components
- [ ] Split LegDetailPage.tsx into sub-components
- [ ] Update component tests
- [ ] Document component architecture

**Success Metrics:**

- All component files < 250 lines
- No visual regressions
- Improved Lighthouse scores (optional)

### Phase 4: Documentation Reorganization (Weeks 10-11)

**Deliverables:**

- [ ] Create new documentation directory structure
- [ ] Split large markdown files (design-document.md, etc.)
- [ ] Update INDEX.md with new navigation
- [ ] Fix all cross-references
- [ ] Run markdownlint on all docs

**Success Metrics:**

- All documentation files < 500 lines
- No broken links
- Improved documentation discoverability (survey team)

### Phase 5: Continuous Improvement (Ongoing)

**Deliverables:**

- [ ] Monthly code quality reviews
- [ ] Quarterly refactoring sprints
- [ ] Update linting rules based on team feedback
- [ ] Maintain documentation freshness

**Success Metrics:**

- Code quality metrics improve over time
- Developer satisfaction with codebase increases
- Fewer bugs introduced in new features

---

## 7. References and Resources

### Official Documentation

- **FastAPI Best Practices:**
  <https://fastapi.tiangolo.com/tutorial/bigger-applications/>
- **React Component Design:** <https://react.dev/learn/thinking-in-react>
- **Black Formatter:** <https://black.readthedocs.io/>
- **Ruff Linter:** <https://docs.astral.sh/ruff/>
- **Prettier:** <https://prettier.io/docs/en/>
- **Pre-Commit Framework:** <https://pre-commit.com/>

### Books and Articles

- **"Refactoring: Improving the Design of Existing Code"** by Martin Fowler
- **"Working Effectively with Legacy Code"** by Michael Feathers
- **"Clean Code"** by Robert C. Martin
- **"The Pragmatic Programmer"** by Hunt & Thomas

### Tools

- **pytest:** <https://docs.pytest.org/> (Python testing)
- **React Testing Library:** <https://testing-library.com/react> (React testing)
- **markdownlint:** <https://github.com/DavidAnson/markdownlint> (Markdown
  linting)
- **Conventional Commits:** <https://www.conventionalcommits.org/>

---

## 8. Appendix: Quick Reference

### Cheat Sheet: Refactoring Decision Tree

```text
Is the file > 300 lines?
├─ YES → Consider splitting
│   ├─ Python API file? → Route-based decomposition
│   ├─ React component? → Custom hooks + sub-components
│   └─ Markdown doc? → Sub-document strategy
└─ NO → Keep as-is, focus on other quality improvements

Does the code have test coverage?
├─ YES → Safe to refactor
└─ NO → Add tests first, then refactor

Is the change behavior-preserving?
├─ YES → Refactor in small increments
└─ NO → Split into two PRs (refactor + feature)
```

### Command Reference

```bash
# Python formatting
black backend/
ruff check --fix backend/

# Frontend formatting
cd frontend/mission-planner && npx prettier --write "src/**/*.{ts,tsx}"

# Markdown linting
npx markdownlint --fix docs/

# Pre-commit hooks
pre-commit install
pre-commit run --all-files

# Run tests
pytest backend/tests
cd frontend/mission-planner && npm test
```

### PR Templates

**Refactoring PR Title Format:**

```text
refactor(scope): brief description

Examples:
- refactor(routes): extract route statistics endpoints
- refactor(pois): move ETA calculations to service layer
- refactor(docs): split API reference into focused documents
```

**Refactoring PR Description Template:**

```markdown
## Refactoring Summary

**What:** Brief description of what was refactored

**Why:** Reason for refactoring (reduce complexity, improve testability, etc.)

**How:** High-level approach (extract method, split component, etc.)

## Changes

- [ ] Extracted X into Y
- [ ] Moved Z to A
- [ ] Renamed B to C

## Testing

- [ ] All existing tests pass
- [ ] No new tests required (behavior-preserving)
- [ ] Manual testing performed (if applicable)

## Checklist

- [ ] Code is formatted (pre-commit hooks passed)
- [ ] No regressions detected
- [ ] Documentation updated (if applicable)
```

---

Document End
