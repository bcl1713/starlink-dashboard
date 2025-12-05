# Tasks: Documentation Cleanup and Restructuring

**Input**: Design documents from `/specs/002-docs-cleanup/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Not applicable - this is a documentation reorganization effort. Validation is manual navigation testing and automated link checking.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each organizational improvement.

---

## 🎯 Current Status (2025-12-04)

**Progress**: 44 of 83 tasks complete (53%)

**✓ Completed Phases**:
- Phase 1-2: Setup & Foundational Structure (16 tasks)
- Phase 3: User Story 1 - New Developer Onboarding (12 tasks) ✓ MVP
- Phase 4: User Story 2 - Documentation Maintenance (16 tasks) ✓ MVP

**📋 Next Session**:
- Phase 5: User Story 3 - User/Operator Reference (T045-T056) - 12 tasks
- Phase 6: User Story 4 - API Consumer Integration (T057-T066) - 10 tasks
- Phase 7: Polish & Cross-Cutting Concerns (T067-T083) - 17 tasks

**Key Achievements**:
- Created CONTRIBUTING.md with comprehensive documentation guidelines
- Updated all category READMEs with contributor guidance
- Fixed all links in moved historical reports
- Moved docs/exporter/ to docs/reports/analysis-reports/
- Established clear documentation structure for maintainability

---

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

This feature reorganizes documentation only. Primary paths:
- **Root level**: Only README.md, CLAUDE.md, AGENTS.md, CONTRIBUTING.md
- **Main docs**: docs/ with 7 categories (setup, api, features, troubleshooting, architecture, development, reports)
- **Backend docs**: backend/starlink-location/docs/ (service-specific only)
- **Specs**: specs/ (feature planning, no changes)

---

## Phase 1: Setup & Analysis

**Purpose**: Prepare for reorganization by auditing current state and identifying issues

- [X] T001 Audit all markdown files in repository (exclude node_modules, .venv) and create inventory at specs/002-docs-cleanup/file-inventory.txt
- [X] T002 [P] Identify exact duplicate files using md5sum and document in specs/002-docs-cleanup/duplicates-exact.txt
- [X] T003 [P] Identify semantic duplicates (errors docs, features docs) and document in specs/002-docs-cleanup/duplicates-semantic.txt
- [X] T004 [P] Map all internal markdown links using ripgrep and create specs/002-docs-cleanup/links-inventory.txt
- [X] T005 [P] Identify root-level markdown files (excluding README, CLAUDE, AGENTS, CONTRIBUTING) for relocation in specs/002-docs-cleanup/root-level-violations.txt
- [X] T006 [P] Review backend/starlink-location/docs/ and categorize as service-specific vs. project-wide in specs/002-docs-cleanup/backend-docs-analysis.txt
- [X] T007 Create documentation file size report to identify files >280 lines at specs/002-docs-cleanup/file-sizes.txt

**Checkpoint**: Audit complete - we know exactly what needs to move, merge, or split

---

## Phase 2: Foundational Structure

**Purpose**: Create category structure that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until category structure exists

- [X] T008 Create docs/setup/README.md with category index per data-model.md template
- [X] T009 [P] Create docs/api/README.md with category index per data-model.md template
- [X] T010 [P] Create docs/features/README.md with category index per data-model.md template
- [X] T011 [P] Create docs/troubleshooting/README.md with category index per data-model.md template
- [X] T012 [P] Create docs/architecture/README.md with category index per data-model.md template
- [X] T013 [P] Create docs/development/README.md with category index per data-model.md template
- [X] T014 [P] Create docs/reports/README.md with category index per data-model.md template
- [X] T015 Create docs/reports/implementation-reports/ subdirectory for historical artifacts
- [X] T016 [P] Create docs/reports/analysis-reports/ subdirectory for feature analysis artifacts

**Checkpoint**: Foundation ready - all 7 categories exist with README.md indexes

---

## Phase 3: User Story 1 - New Developer Onboarding (Priority: P1) 🎯 MVP

**Goal**: Enable new developers to find setup, architecture, and contribution docs within 10 minutes

**Independent Test**: Provide new developer with repository URL only. Measure time to locate: (1) setup guide, (2) architecture overview, (3) contribution guidelines. Must be <10 minutes.

### Core Documentation Organization for Onboarding

- [X] T017 [P] [US1] Move docs/QUICK-START.md to docs/setup/quick-start.md using git mv
- [X] T018 [P] [US1] Remove docs/SETUP-GUIDE.md (redirect file, target already exists)
- [X] T019 [P] [US1] Move docs/design-document.md to docs/architecture/design-document.md using git mv
- [X] T020 [P] [US1] Move docs/development-workflow.md to docs/development/workflow.md using git mv
- [X] T021 [US1] Update links IN moved files (T017-T020) to use correct relative paths from new locations
- [X] T022 [US1] Update links TO moved files across all documentation using ripgrep search + replace
- [X] T023 [US1] Update README.md links to point to new locations (docs/setup/, docs/architecture/, CONTRIBUTING.md)
- [X] T024 [US1] Update docs/setup/README.md to list all setup documentation with descriptions
- [X] T025 [US1] Update docs/architecture/README.md to list architecture documentation
- [X] T026 [US1] Update docs/development/README.md to list development workflow docs
- [X] T027 [US1] Validate all links for US1 moved files using markdown-link-check or manual script
- [X] T028 [US1] Test onboarding navigation path: README → setup → architecture → CONTRIBUTING

**Checkpoint**: New developers can navigate from README to essential onboarding docs in <10 minutes

---

## Phase 4: User Story 2 - Documentation Maintenance (Priority: P1)

**Goal**: Enable developers to find exactly where to add/update docs without creating duplicates

**Independent Test**: Ask developer to document hypothetical new API endpoint. Verify they navigate to docs/api/ and find consistent examples. Time must be <5 minutes, no duplicate file created.

### Consolidate Duplicates & Create Clear Structure

- [X] T029 [P] [US2] Move FEATURES.md to docs/features/overview.md using git mv
- [X] T030 [P] [US2] Delete or move duplicate FEATURES.md after consolidation in T029
- [X] T031 [P] [US2] Consolidate 7 API error documentation files (docs/api/errors.md, ERRORS.md, errors-*.md) into single docs/api/errors-reference.md
- [X] T032 [P] [US2] Delete consolidated error doc duplicates after merging to errors-reference.md in T031
- [X] T033 [US2] Move root-level IMPLEMENTATION-COMPLETION-SUMMARY.md to docs/reports/implementation-reports/2025-12-03-001-codebase-cleanup-summary.md using git mv
- [X] T034 [P] [US2] Move root-level MARKDOWN-REORGANIZATION-REPORT.md to docs/reports/implementation-reports/2025-12-04-markdown-reorganization.md using git mv
- [X] T035 [P] [US2] Move root-level MARKDOWN-SPLIT-SUMMARY.md to docs/reports/implementation-reports/2025-12-04-markdown-split-summary.md using git mv
- [X] T036 [US2] Update links IN moved historical reports (T033-T035) to use correct relative paths
- [X] T037 [US2] Update links TO moved reports across all documentation
- [X] T038 [US2] Move docs/exporter/ analysis documents to docs/reports/analysis-reports/ (feature-specific artifacts)
- [X] T039 [US2] Update docs/api/README.md to clearly show where to add new endpoint docs (with examples)
- [X] T040 [US2] Update docs/features/README.md to show feature documentation structure
- [X] T041 [US2] Update docs/reports/README.md to list all historical artifacts with dates
- [X] T042 [US2] Add documentation structure guidelines section to CONTRIBUTING.md (reference quickstart.md and data-model.md)
- [X] T043 [US2] Validate all links for US2 changes using markdown-link-check
- [X] T044 [US2] Test documentation maintenance path: Developer finds api/ category → sees examples → adds doc in correct location

**Checkpoint**: Developers know where every type of documentation belongs, duplicates eliminated

---

## Phase 5: User Story 3 - User/Operator Reference (Priority: P2)

**Goal**: Enable operators to find setup, config, and troubleshooting guides organized by task

**Independent Test**: Provide operator with deployment scenario. Measure time to find: (1) installation guide, (2) configuration docs, (3) troubleshooting for specific error. Must be <2 minutes each.

### Organize User-Facing Documentation

- [ ] T045 [P] [US3] Move docs/setup/configuration.md to docs/setup/ if not already there (verify location)
- [ ] T046 [P] [US3] Move docs/TROUBLESHOOTING.md to docs/troubleshooting/quick-diagnostics.md using git mv
- [ ] T047 [P] [US3] Consolidate backend troubleshooting: Review backend/starlink-location/TROUBLESHOOTING.md, move project-wide content to docs/troubleshooting/, keep service-specific
- [ ] T048 [P] [US3] Organize docs/troubleshooting/services/ subdirectory with per-service troubleshooting (grafana.md, prometheus.md, backend.md, frontend.md)
- [ ] T049 [P] [US3] Organize docs/troubleshooting/connectivity/ subdirectory for connectivity issues (live-mode.md, performance.md, data-storage.md)
- [ ] T050 [US3] Update links IN moved troubleshooting files (T046-T049) to use correct relative paths
- [ ] T051 [US3] Update links TO moved troubleshooting files across all documentation
- [ ] T052 [US3] Update docs/setup/README.md to list all setup/configuration guides with clear purpose statements
- [ ] T053 [US3] Update docs/troubleshooting/README.md with symptom-based navigation (by service, by symptom, quick diagnostics)
- [ ] T054 [US3] Ensure docs/features/ clearly separates user-facing feature descriptions from developer implementation details
- [ ] T055 [US3] Validate all links for US3 changes using markdown-link-check
- [ ] T056 [US3] Test operator navigation path: docs/ → setup/ → configuration → troubleshooting/ (each <2 minutes)

**Checkpoint**: Operators can quickly find operational guides without wading through developer docs

---

## Phase 6: User Story 4 - API Consumer Integration (Priority: P2)

**Goal**: Enable API consumers to find complete endpoint docs, models, and examples without encountering duplicates

**Independent Test**: Provide API consumer with integration task ("retrieve mission data"). Measure time to find endpoint spec, model schema, and code example using only documentation. Must be <5 minutes.

### Consolidate & Organize API Documentation

- [ ] T057 [P] [US4] Verify docs/api/endpoints/ structure, ensure all endpoint docs are organized by functional area (missions, pois, routes, eta, etc.)
- [ ] T058 [P] [US4] Verify docs/api/models/ structure, ensure all model/schema docs are clearly named and organized
- [ ] T059 [P] [US4] Verify docs/api/examples/ structure (curl-examples.md, python-examples.md, javascript-examples.md)
- [ ] T060 [P] [US4] Review API-REFERENCE-INDEX.md and ensure it links to organized endpoint, model, and example sections
- [ ] T061 [P] [US4] Check for any remaining duplicate API documentation and consolidate (building on T031-T032 error docs work)
- [ ] T062 [US4] Ensure docs/api/README.md provides clear navigation: endpoints by area → models → examples
- [ ] T063 [US4] Add "Getting Started with API" section to docs/api/README.md with authentication, common patterns, error handling
- [ ] T064 [US4] Update docs/features/ to clearly link to relevant API documentation for each feature
- [ ] T065 [US4] Validate all API documentation links using markdown-link-check
- [ ] T066 [US4] Test API consumer path: docs/api/ → find endpoint category → find model schema → find code example (<5 minutes total)

**Checkpoint**: API consumers can navigate API docs and integrate successfully using only documentation

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Complete documentation index, validate entire structure, ensure compliance

- [ ] T067 [P] Update docs/INDEX.md with complete navigation to all 7 categories and their purposes
- [ ] T068 [P] Add audience-based navigation to docs/INDEX.md (users vs developers vs API consumers)
- [ ] T069 [P] Verify root-level compliance: Only README.md, CLAUDE.md, AGENTS.md, CONTRIBUTING.md exist at root
- [ ] T070 [P] Verify all category README.md files have complete file listings with descriptions
- [ ] T071 [P] Verify all moved files preserve git history using `git log --follow [file]`
- [ ] T072 [P] Run comprehensive link validation across all documentation files using markdown-link-check
- [ ] T073 [P] Verify file size compliance: All docs ≤300 lines or have justification comment
- [ ] T074 [P] Verify category file counts: All categories have <15 top-level files
- [ ] T075 [P] Verify backend documentation separation: Only service-specific docs remain in backend/starlink-location/docs/
- [ ] T076 [P] Verify historical documents have dates and COMPLETE/ARCHIVED status
- [ ] T077 [P] Check for any TEMP- or WIP- files outside docs/reports/temp/
- [ ] T078 [P] Verify all documentation follows lowercase-with-hyphens naming convention
- [ ] T079 [P] Run contract validation scripts from contracts/category-requirements.md
- [ ] T080 [P] Test navigation paths for all 4 user stories to verify independent test criteria
- [ ] T081 Update specs/002-docs-cleanup/quickstart.md with any lessons learned or final structure notes
- [ ] T082 Commit all changes with message following git commit guidelines (file moves + link updates atomic)
- [ ] T083 Create validation report at specs/002-docs-cleanup/validation-report.md documenting compliance with all success criteria

**Checkpoint**: Documentation structure complete, validated, and compliant with all contracts

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup & Analysis (Phase 1)**: No dependencies - can start immediately
- **Foundational Structure (Phase 2)**: Depends on Phase 1 analysis - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Phase 2 foundational structure
- **User Story 2 (Phase 4)**: Depends on Phase 2 foundational structure (can run parallel with US1)
- **User Story 3 (Phase 5)**: Depends on Phase 2 foundational structure (can run parallel with US1, US2)
- **User Story 4 (Phase 6)**: Depends on Phase 2 foundational structure (can run parallel with US1, US2, US3)
- **Polish (Phase 7)**: Depends on all user stories (Phase 3-6) being complete

### User Story Dependencies

- **User Story 1 (P1 - Onboarding)**: Independent - focuses on setup, architecture, contribution docs
- **User Story 2 (P1 - Maintenance)**: Independent - focuses on duplicates, structure guidelines, but shares some files with US1 (links)
- **User Story 3 (P2 - Operator Reference)**: Independent - focuses on user-facing operational docs
- **User Story 4 (P2 - API Consumer)**: Independent - focuses on API reference documentation

**Key Independence**: Each user story reorganizes different documentation areas. Link updates in Phase 7 ensure all links work across stories.

### Within Each User Story

- File moves using `git mv` come first
- Link updates in moved files come second
- Link updates to moved files from other docs come third
- Category README updates come fourth
- Validation comes last

### Parallel Opportunities

**Phase 1 (Analysis)**: T002, T003, T004, T005, T006, T007 can all run in parallel

**Phase 2 (Foundational)**: T009-T014, T016 can run in parallel after T008 (category READMEs)

**Phase 3 (US1)**: T017, T018, T019, T020 can run in parallel (different file moves)

**Phase 4 (US2)**: T029, T030, T031, T032, T034, T035 can run in parallel (different files)

**Phase 5 (US3)**: T045, T046, T047, T048, T049 can run in parallel (different documentation areas)

**Phase 6 (US4)**: T057, T058, T059, T060, T061 can run in parallel (API documentation review/organization)

**Phase 7 (Polish)**: T067-T080 can run in parallel (independent validation tasks)

**User Stories**: Once Phase 2 complete, ALL user stories (Phase 3-6) can run in parallel if team capacity allows

---

## Parallel Example: User Story 1 (New Developer Onboarding)

```bash
# Launch all file moves for User Story 1 together:
Task: "Move docs/QUICK-START.md to docs/setup/quick-start.md using git mv"
Task: "Move docs/SETUP-GUIDE.md to docs/setup/installation.md using git mv"
Task: "Move docs/design-document.md to docs/architecture/design-document.md using git mv"
Task: "Move docs/development-workflow.md to docs/development/workflow.md using git mv"

# Then sequentially: Update links IN moved files, then TO moved files, then validate
```

## Parallel Example: Phase 7 (Polish)

```bash
# Launch all validation tasks together:
Task: "Update docs/INDEX.md with complete navigation"
Task: "Verify root-level compliance"
Task: "Run comprehensive link validation"
Task: "Verify file size compliance"
Task: "Verify category file counts"
Task: "Run contract validation scripts"
# All can run in parallel as they're independent verification tasks
```

---

## Implementation Strategy

### MVP First (User Stories 1 & 2 - Both P1)

1. Complete Phase 1: Setup & Analysis
2. Complete Phase 2: Foundational Structure (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (New Developer Onboarding)
4. Complete Phase 4: User Story 2 (Documentation Maintenance)
5. **STOP and VALIDATE**: Test both P1 stories independently (onboarding + maintenance paths)
6. Merge and deploy if validation passes

**Rationale**: Both P1 stories are critical for project health. US1 helps new contributors, US2 prevents future documentation drift.

### Incremental Delivery

1. **Foundation** (Phase 1-2): Category structure exists, ready for organization
2. **MVP** (Phase 3-4): New developers can onboard, existing developers know where to add docs
3. **User Reference** (Phase 5): Operators can find operational guides easily
4. **API Docs** (Phase 6): API consumers can integrate successfully
5. **Validated** (Phase 7): All contracts satisfied, links validated, structure complete

### Parallel Team Strategy

With multiple developers (after Phase 2 complete):

1. **Developer A**: Phase 3 (User Story 1 - Onboarding)
2. **Developer B**: Phase 4 (User Story 2 - Maintenance)
3. **Developer C**: Phase 5 (User Story 3 - Operator Reference)
4. **Developer D**: Phase 6 (User Story 4 - API Consumer)
5. **All developers**: Phase 7 (Polish) - divide validation tasks

Each developer works independently, commits to feature branch, merge after Phase 7 validation.

---

## Notes

### Task Format Compliance

- **All tasks** follow format: `- [ ] [ID] [P?] [Story?] Description with file path`
- **[P] markers**: Different files, no dependencies, can run in parallel
- **[Story] markers**: US1 (Onboarding), US2 (Maintenance), US3 (Operator), US4 (API Consumer)
- **File paths**: Specific paths provided for all file operations (moves, creates, updates)

### Commit Strategy

- **Atomic commits**: File move + link updates in same commit to avoid broken links
- **Git mv always**: Preserves history for all file relocations
- **Commit message format**: Follow project conventions, include file paths and rationale

### Validation Requirements

Each user story MUST pass independent test before merge:
- **US1**: New developer navigation test (<10 minutes to find setup, architecture, contribution)
- **US2**: Developer maintenance test (<5 minutes to find where to add API doc, no duplicates created)
- **US3**: Operator reference test (<2 minutes each for setup, config, troubleshooting)
- **US4**: API consumer integration test (<5 minutes to find endpoint, model, example)

### Success Criteria Mapping

- **SC-001** (10-minute onboarding): User Story 1 (Phase 3)
- **SC-002** (root-level compliance): User Story 2 (Phase 4, validated in Phase 7)
- **SC-003** (zero broken links): All phases, validated in Phase 7 (T072)
- **SC-004** (2-minute search): User Stories 1-4, validated in Phase 7 (T080)
- **SC-005** (zero duplicates): User Story 2 (Phase 4)
- **SC-006** (clear INDEX): Phase 7 (T067-T068)
- **SC-007** (<15 files per category): Phase 7 (T074)
- **SC-008** (clear purpose statements): All user stories, validated in Phase 7 (T070)
- **SC-009** (backend separation): User Story 2 (Phase 4, T047) + Phase 7 (T075)
- **SC-010** (historical artifacts): User Story 2 (Phase 4, T033-T035, T041)

---

## Total Task Summary

- **Phase 1**: 7 tasks (Setup & Analysis)
- **Phase 2**: 9 tasks (Foundational Structure)
- **Phase 3**: 12 tasks (User Story 1 - Onboarding)
- **Phase 4**: 16 tasks (User Story 2 - Maintenance)
- **Phase 5**: 12 tasks (User Story 3 - Operator Reference)
- **Phase 6**: 10 tasks (User Story 4 - API Consumer)
- **Phase 7**: 17 tasks (Polish & Validation)

**Total**: 83 tasks

**Parallel Opportunities**: 45 tasks marked [P] can run in parallel within their phases

**MVP Scope**: Phases 1-4 (44 tasks) deliver both P1 user stories

**Independent Stories**: All 4 user stories can be implemented and tested independently after Phase 2
