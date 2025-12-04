# Implementation Plan: Codebase Cleanup and Refactoring

**Branch**: `001-codebase-cleanup` | **Date**: 2025-12-02 | **Spec**:
[spec.md](./spec.md) **Input**: Feature specification from
`/specs/001-codebase-cleanup/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See
`.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Systematic refactoring of the Starlink Dashboard codebase to achieve
constitutional compliance across backend Python, frontend TypeScript/React, and
documentation. Primary goals: bring 80% of files (21 of 26) under 300 lines, add
type hints and docstrings to all refactored code, ensure linting compliance, and
improve SOLID design principles. Work proceeds incrementally via small PRs (1-3
files) with manual smoke testing and CI/CD quality gates.

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript/React (frontend),
Markdown (docs) **Primary Dependencies**: FastAPI (backend), React/Vite
(frontend), Black, Prettier, ESLint, markdownlint-cli2 **Storage**: N/A
(refactoring existing code, no new data storage) **Testing**: pytest (Python),
manual smoke testing per PR, existing test suite maintenance **Target
Platform**: Linux server (backend Docker), browser (frontend) **Project Type**:
Web application (existing backend + frontend structure) **Performance Goals**:
No performance regression; refactoring must preserve current behavior
**Constraints**:

- Files must be <300 lines (constitutional requirement)
- No feature changes (strict refactoring only)
- 80% compliance threshold (21 of 26 files)
- PR size limited to 1-3 related files **Scale/Scope**: 26 files requiring
  refactoring (14 backend, 3 frontend, 9 docs)

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

### Core Principles Compliance

✅ **I. Clean, Human-Readable Code**

- **Status**: PRIMARY GOAL - This refactoring directly addresses this principle
- **Actions**: Add type hints, docstrings, clear naming, explanatory comments to
  all refactored code
- **Validation**: FR-005 through FR-012 enforce this principle

✅ **II. Current & Complete Documentation**

- **Status**: PRIMARY GOAL - Documentation accuracy is P3 user story
- **Actions**: Validate and update all docs to match current system state
- **Validation**: FR-013 through FR-017 enforce this principle

✅ **III. Responsive, Appropriately-Themed Interfaces**

- **Status**: NOT APPLICABLE - No UI changes in this refactoring
- **Note**: Frontend refactoring is structural only, no visual/UX changes

⚠️ **IV. File Size Limits for Maintainability**

- **Status**: PRIMARY GOAL - This is the P1 user story and root cause of this
  feature
- **Current Violation**: 26 files exceed 300 lines (largest: 3995 lines)
- **Target**: 80% compliance (21 of 26 files under 300 lines)
- **Justification for <100%**: Per clarification session, 80% threshold
  acceptable with documented justifications for remaining files

### Development & Quality Standards Compliance

✅ **Code Formatting & Linting**

- **Status**: ENFORCED via FR-024 through FR-031
- **Actions**: Black (Python), Prettier (TS/JS/MD), ESLint, markdownlint-cli2
- **CI/CD**: Automated checks on every PR (blocks merge on violations)

✅ **Testing Discipline**

- **Status**: MAINTAINED (existing tests updated, no new test requirements)
- **Actions**: Manual smoke testing per PR per clarification

✅ **Observability & Debugging**

- **Status**: NOT APPLICABLE - No changes to logging/metrics infrastructure

✅ **Versioning & Breaking Changes**

- **Status**: PATCH-level changes (no breaking changes, strict refactoring)

### Governance Compliance

✅ **Constitution Compliance Check**

- **Status**: This feature IS the compliance mechanism
- **Process**: Each PR will demonstrate progress toward constitutional
  compliance
- **Tracking**: Complexity Tracking table below documents the current violation
  state

✅ **Justification Requirement**

- **Met**: See Complexity Tracking section and Known Violations in spec.md
- **Rationale**: 26 files currently violate Principle IV; 80% reduction is
  pragmatic goal

### Gate Result: ✅ PASS

This refactoring feature exists specifically to address constitutional
violations. The 80% compliance threshold is justified as a pragmatic
intermediate goal given the scale of violations (largest file is 13x over
limit).

## Project Structure

### Documentation (this feature)

```text
specs/001-codebase-cleanup/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output (refactoring strategies)
├── data-model.md        # Phase 1 output (file/task tracking model)
├── quickstart.md        # Phase 1 output (refactoring workflow guide)
├── contracts/           # Phase 1 output (validation schemas)
└── tasks.md             # Phase 2 output (/speckit.tasks - NOT YET CREATED)
```

### Source Code (repository root)

```text
# Existing Web Application Structure (NO CHANGES to structure)

backend/
├── starlink-location/
│   └── app/
│       ├── api/          # 4 files to refactor (ui.py, pois.py, routes.py, ...)
│       ├── mission/      # 5 files to refactor (exporter.py, timeline_service.py, ...)
│       ├── services/     # 5 files to refactor (kml_parser.py, eta_calculator.py, ...)
│       └── core/         # 1 file to refactor (metrics.py)

frontend/
├── mission-planner/
│   └── src/
│       ├── components/   # 1 file to refactor (RouteMap.tsx)
│       └── pages/        # 2 files to refactor (LegDetailPage.tsx, SatelliteManagerPage.tsx)

docs/                     # 9 files to refactor (API-REFERENCE.md, TROUBLESHOOTING.md, ...)
```

**Structure Decision**: Existing web application structure is maintained.
Refactoring will split large files into smaller modules within the same
directory hierarchy. For example:

- `backend/starlink-location/app/api/ui.py` (3995 lines) → Split into
  `ui/__init__.py`, `ui/routes.py`, `ui/templates.py`, `ui/helpers.py`
- `docs/API-REFERENCE.md` (999 lines) → Split into `docs/api/` directory with
  `endpoints.md`, `models.md`, `errors.md`

## Complexity Tracking

> **Current Constitutional Violations Requiring Justification**

| File                                                        | Current Lines | Target | Violation Type            | Justification                                       | Resolution Plan                                                |
| ----------------------------------------------------------- | ------------- | ------ | ------------------------- | --------------------------------------------------- | -------------------------------------------------------------- |
| `backend/starlink-location/app/api/ui.py`                   | 3995          | 300    | Principle IV (13.3x over) | Monolithic UI route handler with embedded templates | Split into ui/ module with routes, templates, helpers          |
| `backend/starlink-location/app/mission/exporter.py`         | 1927          | 300    | Principle IV (6.4x over)  | Complex mission export logic with multiple formats  | Extract format handlers into exporter/ module                  |
| `backend/starlink-location/app/mission/timeline_service.py` | 1439          | 300    | Principle IV (4.8x over)  | Timeline calculation with state management          | Split into timeline/ module with calculator, state, validators |
| `backend/starlink-location/app/mission/package_exporter.py` | 1291          | 300    | Principle IV (4.3x over)  | Mission package assembly and compression            | Extract into package/ module with builders, compressors        |
| `backend/starlink-location/app/mission/routes.py`           | 1192          | 300    | Principle IV (4.0x over)  | All mission API endpoints in one file               | Split by resource: missions, legs, waypoints                   |
| `backend/starlink-location/app/mission/routes_v2.py`        | 1104          | 300    | Principle IV (3.7x over)  | Mission v2 API endpoints                            | Split by resource, consolidate with routes.py                  |
| `backend/starlink-location/app/api/pois.py`                 | 1092          | 300    | Principle IV (3.6x over)  | POI CRUD operations and calculations                | Split into pois/ module with crud, calculations, validators    |
| `backend/starlink-location/app/api/routes.py`               | 1046          | 300    | Principle IV (3.5x over)  | Route API endpoints                                 | Split by operation: upload, manage, activate                   |
| `backend/starlink-location/app/services/kml_parser.py`      | 1008          | 300    | Principle IV (3.4x over)  | KML parsing with validation and transformation      | Extract into kml/ module with parser, validator, transformer   |
| 17 additional files                                         | 300-850       | 300    | Principle IV (moderate)   | Various violations                                  | See Known Violations in spec.md                                |

**Total Violations**: 26 files **Target Resolution**: 21 files (80% compliance
threshold) **Deferred**: Up to 5 most complex files may be documented and
tracked in follow-up issues

**Simpler Alternative Rejected**: 100% compliance was considered but rejected
because:

- Risk too high for files exceeding 1000 lines (potential for breaking changes)
- Time-to-value tradeoff: 80% compliance delivers significant benefit with lower
  risk
- Remaining 20% can be addressed in follow-up with more thorough testing
  infrastructure

---

## Phase 0: Research - COMPLETED ✅

**Objective**: Resolve all technical unknowns and establish refactoring
strategies

**Deliverables**:

- ✅ research.md (40 KB) - Comprehensive refactoring strategies

**Key Decisions**:

1. **Python Module Decomposition**: Route-based decomposition with service layer
   extraction
1. **TypeScript/React Refactoring**: Custom hook extraction + component
   composition
1. **Documentation Organization**: Sub-document strategy with navigation index
1. **Safe Refactoring Workflow**: Incremental refactoring with test-first
   verification
1. **Linting Automation**: Pre-commit hooks with CI/CD integration

**All NEEDS CLARIFICATION items resolved**: Yes

---

## Phase 1: Design & Contracts - COMPLETED ✅

**Objective**: Define data models, validation contracts, and implementation
workflow

**Deliverables**:

- ✅ data-model.md (33 KB) - Four core entities with state machines
- ✅ contracts/validation-schema.yaml (29 KB) - OpenAPI schema for validation
- ✅ contracts/linting-config-requirements.md (17 KB) - Tool configurations and
  CI/CD specs
- ✅ contracts/smoke-test-checklist.md (20 KB) - Standardized manual test
  procedures
- ✅ quickstart.md (59 KB) - Step-by-step refactoring workflow guide
- ✅ Agent context updated in CLAUDE.md

**Constitution Re-Check**: ✅ PASS (no changes from initial check)

---

## Phase 2: Task Generation - NEXT STEP

**Status**: Ready for `/speckit.tasks` command

**Prerequisites**: All Phase 0 and Phase 1 artifacts complete ✅

**Expected Output**: tasks.md with dependency-ordered refactoring tasks for all
26 violating files

**Estimated Task Count**: 50-75 tasks (assessment, refactoring, validation per
file group)

---

## Implementation Readiness

**Branch**: `001-codebase-cleanup` ✅  
**Specification**: Complete with 5 clarifications ✅  
**Technical Context**: Fully defined ✅  
**Research**: Complete with decisions and rationale ✅  
**Data Model**: Defined with state machines ✅  
**Validation Contracts**: Production-ready schemas ✅  
**Workflow Guide**: Comprehensive quickstart ✅  
**Agent Context**: Updated ✅

**Status**: 🟢 **READY FOR TASK GENERATION**

Run `/speckit.tasks` to generate the implementation task list.
