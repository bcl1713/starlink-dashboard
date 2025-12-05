# Implementation Plan: Documentation Cleanup and Restructuring

**Branch**: `002-docs-cleanup` | **Date**: 2025-12-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-docs-cleanup/spec.md`

## Summary

Reorganize all project markdown documentation into a coherent, navigable structure within the docs/ folder. Remove root-level documentation clutter, eliminate duplicates, consolidate fragmented documentation, update all internal links, and establish clear documentation structure guidelines to prevent future drift. This effort builds on 001-codebase-cleanup quality standards and focuses exclusively on documentation organization (not content accuracy audits).

## Technical Context

**Language/Version**: Markdown (CommonMark specification)
**Primary Dependencies**: ripgrep (rg) for search, git mv for preserving history
**Storage**: Filesystem-based markdown files in docs/ hierarchy
**Testing**: Manual link validation, grep-based duplicate detection, navigation path testing
**Target Platform**: Git repository, rendered in GitHub/GitLab markdown viewers
**Project Type**: Documentation reorganization (no code changes)
**Performance Goals**: Documentation findable within 2 minutes for common scenarios; setup docs findable within 10 minutes
**Constraints**: Zero content loss, zero broken links, preserve git history, maintain 300-line file size guideline
**Scale/Scope**: ~200+ markdown files across project, docs/, backend/, specs/, with ~50 requiring relocation/consolidation

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

### Gate 1: File Size Compliance (Principle IV)

**Status**: ✓ PASS (with monitoring)

- Target: All markdown files ≤300 lines
- Current state: Most docs comply (from 001-codebase-cleanup effort)
- Risk areas: Some consolidated docs may approach 300 lines after merging duplicates
- **Mitigation**: Monitor file sizes during consolidation; split if >280 lines

### Gate 2: Documentation Currency (Principle II)

**Status**: ⚠ PARTIAL (out of scope by design)

- Target: Documentation MUST be accurate and up-to-date
- Current approach: Organization only, not content accuracy audit
- **Justification**: Content accuracy is a separate effort. This feature focuses on structure to enable future content audits.
- **Mitigation**: Flag obviously outdated content for follow-up; update INDEX.md with accurate navigation

### Gate 3: Clear Documentation (Principle II)

**Status**: ✓ PASS

- Target: Documentation MUST address both developer and user needs
- Approach: Explicit separation of user-facing vs. developer documentation
- Implementation: Separate top-level categories, updated INDEX.md with audience-based navigation

### Gate 4: Runtime Guidance Minimalism (Governance)

**Status**: ✓ PASS

- Target: CLAUDE.md MUST be <300 lines and not duplicate docs/
- Current state: CLAUDE.md is 157 lines (compliant)
- Approach: Ensure documentation consolidation doesn't cause CLAUDE.md growth
- **Mitigation**: Reference docs/ from CLAUDE.md rather than duplicating content

### Gate 5: Zero Breaking Changes (Constraint)

**Status**: ✓ PASS

- Target: All documentation links remain functional
- Approach: Comprehensive link update pass with validation
- Implementation: Search all links, update relative paths, validate with link checker
- **Mitigation**: Commit link updates atomically with file moves

### Complexity Justifications

No constitution violations require justification. This is a documentation reorganization effort that aligns with all constitution principles, particularly Principle II (Current & Complete Documentation).

## Project Structure

### Documentation (this feature)

```text
specs/002-docs-cleanup/
├── spec.md              # Feature specification (completed)
├── checklists/
│   └── requirements.md  # Specification quality checklist (completed)
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (documentation organization patterns)
├── data-model.md        # Phase 1 output (documentation taxonomy)
├── quickstart.md        # Phase 1 output (contributor guide to new structure)
├── contracts/           # Phase 1 output (documentation structure contracts)
│   ├── category-requirements.md
│   └── link-validation-checklist.md
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

This feature reorganizes documentation, not code. The target structure is:

```text
# Root level (minimal documentation)
README.md               # Project overview (RETAINED)
CLAUDE.md              # Runtime guidance (RETAINED)
AGENTS.md              # Agent configuration (RETAINED)
CONTRIBUTING.md        # Contribution guidelines (RETAINED)

# Main documentation hierarchy
docs/
├── INDEX.md           # Master documentation index (UPDATED)
│
├── setup/             # User-facing setup and configuration
│   ├── README.md      # Setup category index
│   ├── quick-start.md
│   ├── installation.md
│   ├── configuration.md
│   └── ...
│
├── api/               # API reference documentation
│   ├── README.md      # API category index
│   ├── endpoints/
│   ├── models/
│   ├── examples/
│   └── ...
│
├── features/          # Feature documentation by capability
│   ├── README.md      # Features category index
│   ├── monitoring.md
│   ├── navigation.md
│   ├── mission-planning.md
│   └── ...
│
├── troubleshooting/   # Operational troubleshooting guides
│   ├── README.md      # Troubleshooting category index
│   ├── services/
│   ├── connectivity/
│   └── ...
│
├── architecture/      # System architecture and design
│   ├── README.md      # Architecture category index
│   ├── design-document.md
│   ├── data-structures/
│   └── ...
│
├── development/       # Developer guides and workflows
│   ├── README.md      # Development category index
│   ├── workflow.md
│   ├── testing.md
│   ├── claude-code/
│   └── ...
│
└── reports/           # Historical reports and retrospectives
    ├── README.md      # Reports category index
    ├── implementation-reports/
    └── analysis-reports/

# Backend-specific documentation (RETAINED if service-specific)
backend/starlink-location/docs/
├── ARCHITECTURE.md    # Backend service architecture
├── TESTING.md         # Backend-specific testing
└── TROUBLESHOOTING.md # Backend-specific troubleshooting

# Specs documentation (RETAINED - feature planning)
specs/
├── 001-codebase-cleanup/
│   ├── spec.md
│   ├── plan.md
│   └── ...
└── 002-docs-cleanup/
    └── ...
```

**Structure Decision**: Reorganize into 7 top-level categories (setup, api, features, troubleshooting, architecture, development, reports) with category-level README.md indexes. Minimize root-level documentation to 4 essential files. Preserve backend/ and specs/ documentation in place.

## Phase 0: Research & Discovery

### Research Tasks

#### R1: Documentation Organization Best Practices

**Objective**: Research industry best practices for technical documentation organization (e.g., Divio documentation system, Microsoft style guide)

**Key Questions**:
- What are standard documentation categories for technical projects?
- How to balance user-facing vs. developer-facing documentation?
- Best practices for documentation indexing and navigation?

**Deliverable**: Summary of documentation taxonomy patterns with recommendations

#### R2: Link Update Strategy

**Objective**: Determine reliable method for updating internal markdown links after file moves

**Key Questions**:
- How to identify all internal links (relative paths, absolute paths, anchor links)?
- What tools can validate link integrity after updates?
- How to handle edge cases (links in code comments, links to anchors)?

**Deliverable**: Link update workflow with tool recommendations

#### R3: Git History Preservation

**Objective**: Confirm approach to preserve git history when moving/renaming files

**Key Questions**:
- Does `git mv` preserve history effectively for markdown files?
- Are there cases where manual moves break history tracking?
- How to structure commits for maximum history preservation?

**Deliverable**: Git workflow recommendations for file moves

#### R4: Duplicate Detection Strategy

**Objective**: Determine method for identifying duplicate or highly similar documentation

**Key Questions**:
- How to detect exact duplicates (file content comparison)?
- How to detect near-duplicates (similar content, different formatting)?
- What tools can assist with similarity detection?

**Deliverable**: Duplicate detection workflow

#### R5: Documentation Categorization Rules

**Objective**: Define clear rules for categorizing documentation into top-level folders

**Key Questions**:
- What criteria distinguish user-facing vs. developer documentation?
- Where do mixed-audience documents belong?
- How to handle historical vs. current documentation?

**Deliverable**: Categorization decision tree

### Research Output

**File**: `research.md`

**Contents**:
- R1: Documentation taxonomy recommendations (with rationale)
- R2: Link update workflow (tools, process, validation)
- R3: Git file move best practices (preserve history)
- R4: Duplicate detection approach (exact and near-duplicate)
- R5: Categorization decision tree (with examples)

## Phase 1: Design & Contracts

### D1: Documentation Taxonomy (data-model.md)

**Objective**: Define complete taxonomy of documentation categories, file purposes, and organizational rules

**Contents**:
- **Category Definitions**: Each top-level category (setup, api, features, etc.) with purpose and scope
- **File Classification Rules**: How to categorize any documentation file
- **Naming Conventions**: File naming standards for consistency
- **Metadata Requirements**: Required frontmatter/headers for documentation
- **Cross-Reference Strategy**: How to link between categories

**Output**: `data-model.md`

### D2: Documentation Structure Contracts (contracts/)

**Objective**: Define testable contracts for documentation organization

**Contracts**:

1. **Category Requirements** (`contracts/category-requirements.md`):
   - Each category MUST have README.md index
   - Top-level categories MUST contain <15 files
   - Category README MUST list all contained documentation with descriptions
   - Subcategories MUST be used for >15 related documents

2. **Link Validation** (`contracts/link-validation-checklist.md`):
   - All internal links MUST use relative paths
   - All links MUST be validated before merge
   - Broken links MUST block merge
   - Link validation MUST be repeatable (script/tool)

3. **Root-Level Restriction** (in `contracts/category-requirements.md`):
   - ONLY README.md, CLAUDE.md, AGENTS.md, CONTRIBUTING.md at root
   - All other markdown MUST be in docs/, backend/, or specs/
   - Temporary documentation MUST be prefixed with TEMP- and in docs/reports/

4. **Duplicate Prevention** (in `contracts/category-requirements.md`):
   - No two files MUST contain identical content
   - Similar content MUST be consolidated with single authoritative source
   - Historical duplicates MUST be archived, not kept current

**Output**: `contracts/category-requirements.md`, `contracts/link-validation-checklist.md`

### D3: Quick Start for Contributors (quickstart.md)

**Objective**: Guide for developers on new documentation structure

**Contents**:
- Where to find documentation by purpose (setup, API, troubleshooting, etc.)
- Where to add new documentation (decision flowchart)
- How to update documentation links
- How to validate changes before committing
- Reference to CONTRIBUTING.md for full guidelines

**Output**: `quickstart.md`

### D4: Agent Context Update

**Objective**: Update Claude Code agent context with documentation structure

**Actions**:
- Run `.specify/scripts/bash/update-agent-context.sh claude`
- Add documentation organization patterns to agent context
- Preserve existing manual additions

**Output**: Updated `.claude/context.md` (or equivalent agent file)

## Phase 2: Task Breakdown (via /speckit.tasks)

Phase 2 is NOT part of this plan command. After completing Phase 0-1, run `/speckit.tasks` to generate detailed implementation tasks.

**Expected task categories** (preview):
1. **Analysis Tasks**: Audit current documentation, identify duplicates, map links
2. **Relocation Tasks**: Move root-level docs to appropriate categories
3. **Consolidation Tasks**: Merge duplicate/fragmented documentation
4. **Link Update Tasks**: Update all internal links to new locations
5. **Index Update Tasks**: Update docs/INDEX.md and category README files
6. **Validation Tasks**: Validate links, test navigation paths, verify structure
7. **Guidelines Tasks**: Update CONTRIBUTING.md with documentation structure

## Implementation Notes

### Phasing Strategy

**Phase 0 (Research)**: Complete all research tasks to establish patterns and workflows. No file changes.

**Phase 1 (Design)**: Create taxonomy, contracts, and contributor guide. Minimal file changes (create new documentation, no moves yet).

**Phase 2 (Tasks via /speckit.tasks)**: Break down implementation into atomic tasks. Implementation happens after task generation.

### Risk Mitigation

**Risk: Broken Links**
- Mitigation: Comprehensive link search before and after moves, validation before merge

**Risk: Lost Content**
- Mitigation: Git history preservation, no destructive deletes without review

**Risk: Unclear Categorization**
- Mitigation: Clear categorization rules in data-model.md, decision tree for edge cases

**Risk: Scope Creep (content updates)**
- Mitigation: Strict focus on organization, flag content issues for follow-up

### Success Validation

After implementation (Phase 3+):
1. Verify all success criteria from spec.md
2. Run link validation across all documentation
3. Test navigation paths with new developer persona
4. Verify root-level compliance (only 4 allowed files)
5. Check git history preservation for moved files

## Next Steps

1. Complete Phase 0: Generate `research.md` by researching documentation organization patterns
2. Complete Phase 1: Generate `data-model.md`, contracts, and quickstart guide
3. Run agent context update script
4. Run `/speckit.tasks` to generate detailed implementation task list
5. Begin implementation following generated tasks

---

**Plan Status**: Phase 0 ready to begin
**Blockers**: None
**Dependencies**: None (standalone documentation reorganization)
