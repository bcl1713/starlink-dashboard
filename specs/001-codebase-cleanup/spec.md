# Feature Specification: Codebase Cleanup and Refactoring

**Feature Branch**: `001-codebase-cleanup` **Created**: 2025-12-02 **Status**:
Draft **Input**: User description: "cleanup and refactor - This code base has
gotten messy over time and does not adhere to our constitutional principles. I'd
like to sequentially and methodically work through the entire codebase,
refactoring, and cleaning up the code and documentation to ensure best
practices, SOLID design, etc."

## Clarifications

### Session 2025-12-02

- Q: Refactoring Workflow & Git Strategy → A: One PR per file or small file
  group (1-3 related files) for incremental review and merge
- Q: Testing Strategy for Refactored Code → A: Manual smoke testing per PR to
  verify behavior unchanged
- Q: Handling Breaking Refactors → A: Document breaking points, create follow-up
  issues for complex cases, proceed with safe refactors
- Q: CI/CD Integration Requirements → A: Run linters/formatters (Black,
  Prettier, ESLint, markdownlint) on each PR as quality gates
- Q: Refactoring Completion Threshold → A: 80% compliance threshold acceptable
  (defer hardest cases to follow-up issues)

## User Scenarios & Testing _(mandatory)_

### User Story 1 - File Size Compliance (Priority: P1)

As a developer working on the Starlink Dashboard, I need all source code and
documentation files to be under 300 lines so that I can quickly understand,
modify, and maintain any file without cognitive overload.

**Why this priority**: This is foundational—oversized files violate Constitution
Principle IV and create the biggest barrier to maintainability. Several files
currently exceed 1000 lines, with the largest at 3995 lines.

**Independent Test**: Can be fully tested by running a line count check on all
Python and Markdown files and verifying all are under 300 lines (or have
justified exceptions documented).

**Acceptance Scenarios**:

1. **Given** a Python file exceeding 300 lines, **When** refactoring is
   complete, **Then** the file is split into logical modules each under 300
   lines with clear separation of concerns
1. **Given** a Markdown documentation file exceeding 300 lines, **When**
   refactoring is complete, **Then** the file is split into linked documents or
   sections, maintaining navigation and readability
1. **Given** a file that must exceed 300 lines (e.g., generated code), **When**
   reviewed, **Then** it includes a comment explaining why refactoring was
   deferred

---

### User Story 2 - Code Readability and Documentation (Priority: P2)

As a new developer joining the project, I need code to be self-documenting with
clear names, type hints, and explanatory comments so that I can understand the
"why" behind implementation choices without extensive onboarding.

**Why this priority**: Clean, readable code directly supports Constitution
Principle I and reduces onboarding time. This builds on P1 by improving quality
within the refactored files.

**Independent Test**: Can be tested by code review verification that all
functions have docstrings, type hints are present, comments explain rationale
(not mechanics), and variable/function names are descriptive.

**Acceptance Scenarios**:

1. **Given** a Python function without type hints, **When** refactoring is
   complete, **Then** the function has proper type annotations for parameters
   and return values
1. **Given** a function without a docstring, **When** refactoring is complete,
   **Then** it has a PEP 257 compliant docstring explaining purpose, parameters,
   returns, and any side effects
1. **Given** code with cryptic variable names, **When** refactoring is complete,
   **Then** names clearly indicate purpose and type (e.g., `route_eta_seconds`
   instead of `x`)
1. **Given** comments explaining what code does, **When** refactoring is
   complete, **Then** comments are updated to explain why the approach was
   chosen

---

### User Story 3 - Documentation Accuracy and Completeness (Priority: P3)

As a user or developer referencing documentation, I need all docs to accurately
reflect the current system state so that I don't waste time debugging
discrepancies between documentation and reality.

**Why this priority**: Accurate documentation supports Constitution Principle
II. This builds on P1/P2 work and can be validated after code stabilizes.

**Independent Test**: Can be tested by verifying all API endpoints,
configuration options, and workflows described in documentation match actual
system behavior.

**Acceptance Scenarios**:

1. **Given** documentation describing an API endpoint, **When** validation is
   complete, **Then** the endpoint exists, accepts documented parameters, and
   returns documented responses
1. **Given** a setup guide with configuration steps, **When** validation is
   complete, **Then** following the guide successfully configures the system
1. **Given** architecture documentation with component diagrams, **When**
   validation is complete, **Then** diagrams match actual component
   relationships and data flows
1. **Given** stale comments or outdated examples, **When** refactoring is
   complete, **Then** all inline documentation reflects current code behavior

---

### User Story 4 - SOLID Design Principles (Priority: P4)

As a developer extending functionality, I need code to follow SOLID principles
so that I can add features without causing cascading changes or breaking
existing functionality.

**Why this priority**: SOLID design improves long-term maintainability but
requires stable, readable code first (depends on P1-P2).

**Independent Test**: Can be tested by verifying that single-responsibility
violations are resolved, classes/modules have clear boundaries, and dependencies
are properly injected rather than hardcoded.

**Acceptance Scenarios**:

1. **Given** a class or module with multiple unrelated responsibilities,
   **When** refactoring is complete, **Then** responsibilities are separated
   into focused, single-purpose components
1. **Given** hardcoded dependencies, **When** refactoring is complete, **Then**
   dependencies are injected or configured, enabling easier testing and
   flexibility
1. **Given** functions exceeding 50 lines, **When** refactoring is complete,
   **Then** they are decomposed into smaller, focused functions with clear names
1. **Given** tight coupling between modules, **When** refactoring is complete,
   **Then** modules interact through well-defined interfaces with minimal
   knowledge of internal implementation

---

### Edge Cases

- What happens when a file legitimately needs to exceed 300 lines (e.g.,
  database migrations, generated code)? → Document with justification comment
  and constitution exception
- What happens when refactoring a large file breaks existing functionality? →
  Ensure comprehensive test coverage before refactoring; if risk remains too
  high, document the breaking points, create follow-up issues for deeper
  investigation, and proceed with safer refactors first
- What happens when documentation updates reveal unclear requirements or
  inconsistent behavior? → Create follow-up issues for requirements
  clarification or bug fixes
- What happens when circular dependencies prevent clean module separation? →
  Document dependency graph, identify and break circular references through
  interface extraction or event-based communication; if untangling is too risky,
  create follow-up issue and defer to later phase
- What happens when a refactor is partially complete but cannot be finished
  safely? → Document what was accomplished, add FR-004 justification comment to
  remaining oversized files, create tracking issue with specific blockers

## Requirements _(mandatory)_

### Functional Requirements

#### File Size and Structure

- **FR-001**: All Python source files MUST be under 300 lines, except for
  explicitly justified exceptions (migrations, generated code, lock files)
- **FR-002**: All TypeScript/JavaScript source files MUST be under 300 lines,
  except for explicitly justified exceptions (generated code, package-lock.json)
- **FR-003**: All Markdown documentation files MUST be under 300 lines, using
  linking for longer content
- **FR-004**: Files exceeding 300 lines MUST include a comment explaining why
  refactoring was deferred
- **FR-005**: Large files MUST be decomposed based on logical boundaries (e.g.,
  separate API routes, split React components, extract custom hooks, split
  service responsibilities, extract helper functions)

#### Code Quality and Readability

- **FR-005**: All Python functions MUST have type hints for parameters and
  return values
- **FR-006**: All Python functions MUST have PEP 257 compliant docstrings
- **FR-007**: All TypeScript/JavaScript functions MUST have JSDoc comments for
  exported functions and complex logic
- **FR-008**: All TypeScript code MUST have proper type annotations (avoid `any`
  type unless explicitly justified)
- **FR-009**: Variable and function names MUST be descriptive and indicate
  purpose
- **FR-010**: Functions MUST be under 50 lines (strong preference), with
  exceptions documented
- **FR-011**: Comments MUST explain "why" (rationale) rather than "what"
  (mechanics)
- **FR-012**: Code MUST maintain consistent indentation per project standards (4
  spaces for Python, 2 for TypeScript/JavaScript/YAML/JSON)

#### Documentation Accuracy

- **FR-013**: API documentation MUST match actual endpoint behavior (paths,
  methods, parameters, responses)
- **FR-014**: Configuration documentation MUST reflect all available options and
  their effects
- **FR-015**: Setup guides MUST be validated by successful execution of
  documented steps
- **FR-016**: Architecture diagrams MUST accurately represent current system
  structure
- **FR-017**: Code examples in documentation MUST execute successfully against
  current codebase

#### Design Principles

- **FR-018**: Classes and modules MUST have single, well-defined
  responsibilities
- **FR-019**: React components MUST have single, focused purposes (extract
  sub-components when multiple concerns exist)
- **FR-020**: Dependencies MUST be injected or configured, not hardcoded
- **FR-021**: Modules MUST interact through well-defined interfaces
- **FR-022**: Circular dependencies MUST be eliminated
- **FR-023**: Duplicate code MUST be extracted into shared utilities or custom
  hooks

#### Linting and Formatting

- **FR-024**: All Python code MUST pass Black formatting (line length 88)
- **FR-025**: All TypeScript/JavaScript code MUST pass Prettier formatting
  (print width 80, prose wrap always)
- **FR-026**: All TypeScript/JavaScript code MUST pass ESLint validation
- **FR-027**: All Markdown MUST pass markdownlint-cli2 validation
- **FR-028**: All Markdown MUST pass Prettier formatting (prose wrap always)
- **FR-029**: No inline eslint-disable or markdownlint-disable comments MUST
  remain in code
- **FR-030**: All linting violations MUST be fixed, not suppressed
- **FR-031**: CI/CD pipeline MUST run Black, Prettier, ESLint, and
  markdownlint-cli2 on each PR and block merge if violations detected

### Key Entities

- **Code File**: A source code file (Python, TypeScript, JavaScript) or
  documentation file (Markdown) that is subject to constitution principles; has
  attributes: path, line count, violation status, refactoring priority
- **Refactoring Task**: A specific unit of work to bring a file or module into
  constitutional compliance; has attributes: target file(s), violation type
  (size, documentation, SOLID), estimated effort, dependencies on other tasks
- **Validation Check**: An automated or manual verification that a requirement
  is met; has attributes: requirement ID, check type (line count, linting,
  documentation accuracy), pass/fail status, evidence

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: At least 80% of Python application files (excluding .venv,
  migrations, generated code) are under 300 lines (minimum 21 of 26 identified
  violations resolved)
- **SC-002**: At least 80% of TypeScript/JavaScript application files (excluding
  node_modules, dist, generated code) are under 300 lines
- **SC-003**: At least 80% of Markdown documentation files are under 300 lines
  (or split with linking)
- **SC-004**: 100% of Python functions in refactored files have type hints and
  docstrings
- **SC-005**: 100% of exported TypeScript/JavaScript functions in refactored
  files have JSDoc comments
- **SC-006**: 0 files contain inline lint-disable comments (eslint-disable,
  markdownlint-disable) in refactored code
- **SC-007**: All documented API endpoints return responses matching
  documentation within 5% variance (for metrics)
- **SC-008**: New developer onboarding time reduces by 30% (measured by time to
  first meaningful contribution)
- **SC-009**: Code review cycle time improves by 40% (measured by average time
  from PR creation to approval)
- **SC-010**: 90% of refactored files pass automated readability metrics
  (function length, cyclomatic complexity, documentation coverage)
- **SC-011**: Remaining non-compliant files (up to 20%) have documented
  justifications per FR-004 and tracked follow-up issues

## Assumptions

1. **Scope Boundary**: This refactoring covers the
   `backend/starlink-location/app` directory, `frontend/mission-planner/src`
   directory, and `docs/` directory; third-party libraries, node_modules, .venv,
   and auto-generated files are excluded
1. **Testing Coverage**: Existing tests (if any) will be maintained and updated;
   new tests are not required unless refactoring introduces new logic. Each PR
   will include manual smoke testing to verify behavior remains unchanged
1. **Incremental Approach**: Work will proceed file-by-file in priority order
   (largest violations first), allowing for continuous integration
1. **Git Workflow**: Each refactoring will be submitted as a separate PR
   containing 1-3 related files, enabling focused code review and reducing merge
   conflict risk
1. **No Feature Changes**: This is strictly refactoring—behavior must remain
   identical from a user perspective
1. **Documentation Standard**: Technical accuracy takes precedence over
   completeness—if documentation cannot be validated, it will be marked as
   "requires verification" rather than guessed

## Known Violations (Pre-Refactoring Assessment)

Based on initial codebase scan:

### Backend Python Files

- **Critical Size Violations (>1000 lines)**:
  - `backend/starlink-location/app/api/ui.py` - 3995 lines
  - `backend/starlink-location/app/mission/exporter.py` - 1927 lines
  - `backend/starlink-location/app/mission/timeline_service.py` - 1439 lines
  - `backend/starlink-location/app/mission/package_exporter.py` - 1291 lines
  - `backend/starlink-location/app/mission/routes.py` - 1192 lines
  - `backend/starlink-location/app/mission/routes_v2.py` - 1104 lines
  - `backend/starlink-location/app/api/pois.py` - 1092 lines
  - `backend/starlink-location/app/api/routes.py` - 1046 lines
  - `backend/starlink-location/app/services/kml_parser.py` - 1008 lines

- **Moderate Size Violations (300-1000 lines)**:
  - `backend/starlink-location/app/core/metrics.py` - 850 lines
  - `backend/starlink-location/app/services/eta_calculator.py` - 735 lines
  - `backend/starlink-location/app/services/route_eta_calculator.py` - 652 lines
  - `backend/starlink-location/app/services/poi_manager.py` - 624 lines
  - `backend/starlink-location/app/services/flight_state_manager.py` - 540 lines

### Frontend TypeScript/React Files

- **Moderate Size Violations (300-1000 lines)**:
  - `frontend/mission-planner/src/components/common/RouteMap.tsx` - 482 lines
  - `frontend/mission-planner/src/pages/LegDetailPage.tsx` - 379 lines
  - `frontend/mission-planner/src/pages/SatelliteManagerPage.tsx` - 359 lines

### Documentation Files

- **Moderate Size Violations (300-1000 lines)**:
  - `docs/API-reference.md` - 999 lines
  - `docs/DOCUMENTATION-AUDIT-REPORT.md` - 917 lines
  - `docs/troubleshooting.md` - 816 lines
  - `docs/claude-code-workflows.md` - 731 lines
  - `docs/SETUP-guide.md` - 636 lines
  - `docs/route-timing-guide.md` - 619 lines
  - `docs/mission-visualization-guide.md` - 566 lines
  - `docs/mission-comm-sop.md` - 513 lines
  - `docs/mission-data-structures.md` - 478 lines

**Estimated Violation Count**: 26 files requiring refactoring

- **Backend**: 14 files (9 critical, 5 moderate)
- **Frontend**: 3 files (0 critical, 3 moderate)
- **Documentation**: 9 files (0 critical, 9 moderate)
