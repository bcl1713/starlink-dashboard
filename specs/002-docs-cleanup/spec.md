# Feature Specification: Documentation Cleanup and Restructuring

**Feature Branch**: `002-docs-cleanup`
**Created**: 2025-12-04
**Status**: Draft
**Input**: User description: "clean up documentation. There are lots of random markdown documents throughout the code base. All docs (README, CLAUDE, AGENTS excluded) should live in the docs folder. That folder also needs a large overhaul and cleanup, restructuring to be navigable, discoverable, accurate, and free of extraneous artifacts from previous efforts, and duplicated information"

## User Scenarios & Testing _(mandatory)_

### User Story 1 - New Developer Onboarding (Priority: P1)

A new developer joins the project and needs to understand the system architecture, set up their development environment, and understand how to contribute. They should be able to find all necessary documentation quickly without hunting through scattered markdown files or encountering outdated/duplicate information.

**Why this priority**: First-time user experience is critical for project adoption and developer productivity. Poor documentation organization creates immediate friction and wastes hours of developer time.

**Independent Test**: Can be fully tested by providing a new developer with only the repository URL and measuring time-to-first-contribution. Success means finding setup instructions, architecture overview, and contribution guidelines within 10 minutes.

**Acceptance Scenarios**:

1. **Given** a developer clones the repository, **When** they open README.md, **Then** they see clear links to setup guides, architecture docs, and contribution guidelines
2. **Given** a developer needs to understand the API, **When** they navigate to docs/, **Then** they find a clear API reference structure without duplicate or outdated files
3. **Given** a developer wants to contribute, **When** they look for contribution guidelines, **Then** they find a single authoritative document (not multiple conflicting versions)

---

### User Story 2 - Documentation Maintenance (Priority: P1)

A developer needs to update documentation after making code changes. They should know exactly where documentation lives, avoid creating duplicates, and maintain consistency with existing documentation structure.

**Why this priority**: Poor documentation organization leads to documentation rot, where developers either don't update docs or create duplicate/conflicting documentation.

**Independent Test**: Can be tested by asking a developer to document a new feature and verifying they place documentation in the correct location without creating duplicates or leaving orphaned files.

**Acceptance Scenarios**:

1. **Given** a developer adds a new API endpoint, **When** they look for where to document it, **Then** they find a clear location in docs/api/ with consistent formatting examples
2. **Given** a developer removes deprecated functionality, **When** they search for related docs, **Then** they find all related documentation in predictable locations (not scattered across root and subdirectories)
3. **Given** a developer updates setup procedures, **When** they search for existing setup docs, **Then** they find only one authoritative setup guide (no duplicates)

---

### User Story 3 - User/Operator Reference (Priority: P2)

A system operator or end user needs to set up, configure, or troubleshoot the system. They should find relevant guides organized by task (setup, configuration, troubleshooting) without wading through development-specific documentation.

**Why this priority**: User-facing documentation must be separate from development documentation to avoid confusion and ensure operators can quickly find operational procedures.

**Independent Test**: Can be tested by providing an operator with a deployment scenario and measuring time to find relevant setup, configuration, and troubleshooting documentation.

**Acceptance Scenarios**:

1. **Given** an operator needs to deploy the system, **When** they navigate to docs/, **Then** they find setup documentation clearly separated from development guides
2. **Given** an operator encounters an error, **When** they look for troubleshooting guides, **Then** they find organized troubleshooting by symptom/service (not scattered across multiple locations)
3. **Given** an operator needs to configure a feature, **When** they search for configuration docs, **Then** they find comprehensive configuration guides without duplicate or outdated information

---

### User Story 4 - API Consumer Integration (Priority: P2)

An external developer or system integrator needs to understand and use the REST API. They should find complete, accurate API documentation with examples, without encountering outdated endpoints or conflicting information.

**Why this priority**: API documentation quality directly impacts adoption and reduces support burden. Poor API docs lead to integration failures and support tickets.

**Independent Test**: Can be tested by providing an API consumer with a sample integration task (e.g., "retrieve mission data") and measuring time to successful integration using only documentation.

**Acceptance Scenarios**:

1. **Given** an API consumer needs endpoint documentation, **When** they navigate to docs/api/, **Then** they find comprehensive endpoint documentation organized by functional area
2. **Given** an API consumer needs examples, **When** they look for sample code, **Then** they find working examples in common languages (not scattered or outdated)
3. **Given** an API consumer encounters an error, **When** they check error documentation, **Then** they find a single authoritative error reference (no duplicate error docs)

---

### Edge Cases

- What happens when a document contains both user-facing and developer-facing content? (Split into appropriate sections or create separate focused documents)
- How does system handle historical documentation (implementation reports, retrospectives)? (Move to dedicated archive or reports section with clear dating)
- What happens to temporary artifacts from previous refactoring efforts? (Remove if no longer relevant, archive if historical value)
- How does system prevent future documentation drift? (Establish clear documentation structure and guidelines in CONTRIBUTING.md)

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST relocate all project-level markdown documentation (excluding README.md, CLAUDE.md, AGENTS.md) to the docs/ folder
- **FR-002**: System MUST organize docs/ folder into clear top-level categories (setup, api, features, development, troubleshooting, architecture)
- **FR-003**: System MUST identify and remove duplicate documentation (same content in multiple files)
- **FR-004**: System MUST identify and archive or remove outdated documentation artifacts (temporary reports, obsolete guides)
- **FR-005**: System MUST update all internal documentation links to reflect new file locations
- **FR-006**: System MUST create or update a main documentation index (docs/INDEX.md) with clear navigation paths
- **FR-007**: System MUST separate user-facing documentation (setup, operation, troubleshooting) from developer documentation (architecture, contributing, development guides)
- **FR-008**: System MUST consolidate fragmented documentation (multiple partial guides about the same topic into single authoritative documents)
- **FR-009**: System MUST preserve backend-specific documentation in backend/ directory if it's service-specific implementation detail
- **FR-010**: System MUST identify and mark or remove documentation with outdated information (based on code changes, version mismatches)
- **FR-011**: System MUST ensure each documentation file has a clear single purpose (avoid "misc" or overly broad documents)
- **FR-012**: System MUST update CONTRIBUTING.md with documentation structure guidelines to prevent future drift

### Key Entities

- **Documentation File**: Individual markdown file with metadata (location, purpose, last updated, audience, dependencies)
- **Documentation Category**: Logical grouping of related documentation (API, Setup, Features, etc.)
- **Documentation Link**: Internal reference from one markdown file to another (must remain valid after reorganization)
- **Documentation Artifact**: Historical document from previous efforts (reports, summaries, temporary analysis)
- **Root-level Documentation**: Files at project root (most should move to docs/ except README, CLAUDE, AGENTS)

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: New developers can locate setup instructions, architecture overview, and contribution guidelines within 10 minutes of cloning repository
- **SC-002**: Zero documentation files exist at project root level except README.md, CLAUDE.md, AGENTS.md, and CONTRIBUTING.md
- **SC-003**: All internal documentation links remain functional (zero broken links after reorganization)
- **SC-004**: Documentation search operations (finding specific topics) complete in under 2 minutes for common scenarios (setup, API reference, troubleshooting)
- **SC-005**: Zero duplicate documentation exists (same content in multiple files)
- **SC-006**: Documentation index (docs/INDEX.md) provides clear navigation to all major documentation categories
- **SC-007**: Each documentation category (setup, api, features, troubleshooting) contains less than 15 files at top level (subcategories used for larger collections)
- **SC-008**: 100% of documentation files have clear purpose statements or section headers that immediately communicate content
- **SC-009**: Backend-specific documentation clearly separated from project-wide documentation (95%+ of docs/ content is project-wide)
- **SC-010**: Historical artifacts (implementation reports, temporary summaries) clearly marked with dates and moved to archive/reports section

## Assumptions _(included when relevant)_

1. **Documentation Scope**: This effort focuses on markdown documentation organization, not content accuracy audits. While obvious outdated content will be flagged, comprehensive content review is a separate effort.

2. **Link Update Strategy**: All internal markdown links will be updated using relative paths. External links and code references to documentation are out of scope unless they cause broken builds.

3. **Backend Documentation**: Documentation in backend/starlink-location/docs/ will remain there if it contains service-specific implementation details (architecture, testing, troubleshooting specific to that service). General project information from backend docs will be consolidated into main docs/.

4. **Historical Preservation**: Implementation reports, retrospectives, and phase summaries from previous efforts (001-codebase-cleanup) will be preserved in specs/ or docs/reports/ rather than deleted, as they provide historical context.

5. **Documentation Standards**: Files will follow existing naming conventions and markdown formatting standards established in the project (consistent with current README.md and CLAUDE.md style).

6. **Categorization Principles**:
   - User-facing docs (setup, configuration, operation) separated from developer docs (architecture, contributing, development workflows)
   - API documentation grouped by functional area (endpoints, models, examples)
   - Troubleshooting organized by service/symptom for quick lookup
   - Features documented by major capability area

7. **Migration vs Deletion**: Files will be migrated (not deleted) unless they are:
   - Exact duplicates of other files
   - Temporary artifacts with no historical value (e.g., "TEMP-NOTES.md")
   - Completely superseded by newer comprehensive documentation

8. **Index Strategy**: docs/INDEX.md will serve as the authoritative documentation map, with category-specific indexes (e.g., docs/api/README.md) providing detailed navigation within categories.

## Constraints _(included when relevant)_

1. **Zero Breaking Changes**: All documentation reorganization must preserve content and maintain functioning links. No documentation content can be lost during reorganization.

2. **Automation Limitations**: Link updates may require manual review for complex relative path changes or context-dependent references.

3. **Concurrent Development**: Documentation reorganization must not conflict with ongoing feature development. Clear communication and atomic commits required.

4. **Excluded Files**: README.md, CLAUDE.md, AGENTS.md, CONTRIBUTING.md must remain at project root per user requirements.

5. **Size Constraints**: While reorganizing, maintain or improve upon 300-line-per-file guideline established in 001-codebase-cleanup effort where practical.

6. **Tool Dependencies**: Link validation and updates may depend on available tools (ripgrep for search, markdown link checkers).

## Dependencies _(included when relevant)_

1. **Prior Work**: This effort builds on 001-codebase-cleanup which established file size standards and documentation quality practices.

2. **Documentation Tools**: Requires markdown link validators and search tools (ripgrep) to verify link integrity after reorganization.

3. **Git History**: Must preserve git history for moved files to maintain blame/authorship tracking.

4. **Build System**: Documentation links referenced in code comments or build scripts may need updates (verify with search).

5. **docs/INDEX.md**: Current documentation index exists and will be updated rather than recreated from scratch.

## Out of Scope _(clarifies boundaries)_

1. **Content Accuracy Audit**: Comprehensive review of documentation content for technical accuracy is not included. Only obviously outdated content will be flagged.

2. **Code Documentation**: Inline code comments, docstrings, and API auto-generated documentation are not in scope.

3. **External Documentation**: Documentation hosted on external platforms (wikis, Confluence, etc.) is not in scope.

4. **Visual Documentation**: Diagrams, screenshots, and other non-markdown assets are not reorganized unless they're directly referenced by moved markdown files.

5. **Internationalization**: Translation or multi-language documentation support is not in scope.

6. **Documentation Generation**: Setting up automated documentation generation tools (e.g., Sphinx, MkDocs) is not in scope.

7. **Version-Specific Documentation**: Creating separate documentation for multiple versions is not in scope (single current version only).

## Notes _(optional context)_

### Current State Analysis

Based on repository analysis, the following issues exist:

**Root-level Documentation Clutter** (files that should move to docs/):
- FEATURES.md (duplicates docs/FEATURES-OVERVIEW.md)
- IMPLEMENTATION-COMPLETION-SUMMARY.md (historical artifact from 001-codebase-cleanup)
- MARKDOWN-REORGANIZATION-REPORT.md (historical artifact)
- MARKDOWN-SPLIT-SUMMARY.md (historical artifact)

**docs/ Folder Issues**:
- Deeply nested structures (docs/missions/planning/HELP.md could be docs/mission-planning/help.md)
- Duplicate content areas (docs/api/errors.md, docs/api/ERRORS.md, docs/api/errors-*.md - 7 error-related files)
- Historical artifacts in main docs (docs/documentation-update-summary.md, docs/REORGANIZATION-BATCH-2-SUMMARY.md)
- Unclear categorization (docs/exporter/ contains analysis and planning from feature work, not user-facing docs)

**Backend Documentation**:
- backend/starlink-location/docs/ contains service-specific docs (ARCHITECTURE.md, TESTING.md, TROUBLESHOOTING.md)
- Some duplication with main docs/ (setup, troubleshooting)
- Decision needed: keep backend-specific vs. consolidate project-wide

**Positive Aspects**:
- docs/INDEX.md exists with structured navigation
- Recent 001-codebase-cleanup work established quality standards
- Clear separation of specs/ directory for feature planning

### Reorganization Priorities

1. **High Priority**: Remove root-level clutter (historical reports), consolidate duplicates (errors docs, features docs)
2. **Medium Priority**: Restructure docs/ top-level categories for better discoverability
3. **Low Priority**: Optimize subfolder nesting depth (can be iterative)
