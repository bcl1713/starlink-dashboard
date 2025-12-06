# Phase 0: Research & Discovery

**Feature**: Documentation Cleanup and Restructuring
**Date**: 2025-12-04
**Status**: Complete

## R1: Documentation Organization Best Practices

### Decision: Adopt Modified Divio Documentation System

The Divio documentation system (https://documentation.divio.com) provides a proven framework with 4 documentation types:
- **Tutorials**: Learning-oriented (getting started)
- **How-to Guides**: Task-oriented (operational procedures)
- **Reference**: Information-oriented (technical specifications)
- **Explanation**: Understanding-oriented (architecture, concepts)

### Adaptation for Starlink Dashboard

We'll use a **7-category hybrid system** that maps to project needs:

| Category         | Divio Type    | Audience  | Purpose                          |
| ---------------- | ------------- | --------- | -------------------------------- |
| setup/           | Tutorial      | User      | Getting system running           |
| troubleshooting/ | How-to        | User      | Operational problem-solving      |
| api/             | Reference     | Developer | API specifications and contracts |
| features/        | Explanation   | Both      | Capability descriptions          |
| architecture/    | Explanation   | Developer | System design and decisions      |
| development/     | How-to        | Developer | Development workflows            |
| reports/         | Archive       | Both      | Historical context               |

### Rationale

- **Divio strengths**: Clear separation of concerns, proven in OSS projects
- **Modifications needed**: Add explicit "features" category (common in product docs), separate "reports" for historical artifacts
- **User/developer split**: Categories naturally separate by primary audience while allowing cross-reference

### Alternatives Considered

- **Microsoft Style Guide approach**: Too enterprise-focused, less relevant for OSS
- **Flat structure with tags**: Harder to navigate, requires search/index infrastructure
- **Domain-driven (by feature area)**: Better for multi-product; overkill for single dashboard project

### Implementation Notes

- Each category gets README.md index with clear purpose statement
- Mixed-audience docs (features/) use clear section headers to separate concerns
- Cross-references between categories encouraged via relative links

---

## R2: Link Update Strategy

### Decision: Two-Phase Link Update with Validation

**Phase 1: Discovery**
- Use ripgrep to find all markdown links: `rg '\[.*\]\(.*\.md.*\)' --type md`
- Capture relative paths, absolute paths, and anchor links separately
- Generate link inventory CSV: source_file, link_text, target_path, link_type

**Phase 2: Update & Validate**
- Update links atomically with file moves (same commit)
- Use relative paths exclusively (e.g., `../api/endpoints.md`)
- Validate with markdown-link-check or manual verification script

### Rationale

- **Ripgrep reliability**: Fast, accurate pattern matching across large codebases
- **Atomic commits**: Prevents transient broken link states
- **Relative paths**: Resilient to repository location changes, required for portability

### Tool Recommendations

1. **markdown-link-check** (npm package): Automated validation
   - Pros: Handles relative paths, anchor validation, exit codes for CI
   - Cons: Requires Node.js, slower on large docs

2. **Manual verification script** (bash + rg):
   ```bash
   # Find all markdown links
   rg '\[.*\]\((.*\.md[^)]*)\)' --only-matching --no-filename docs/ | sort -u
   # Check each target exists
   for link in $(cat links.txt); do
     [[ -f "docs/$link" ]] || echo "BROKEN: $link"
   done
   ```

**Recommendation**: Use markdown-link-check for comprehensive validation, fall back to manual script if tooling issues arise.

### Edge Cases

- **Links in code comments**: Out of scope (spec assumption), but flag during discovery
- **External links**: No updates needed, but validate still reachable (optional)
- **Anchor links**: Validate target file has matching header (markdown-link-check handles)

---

## R3: Git History Preservation

### Decision: Use `git mv` with Proper Commit Structure

### Workflow

1. **Single file move**: `git mv old/path.md new/path.md`
   - Preserves full history, git tracks as rename
   - Use `git log --follow new/path.md` to view history

2. **Batch moves** (same category): Commit per category
   ```bash
   # Move all setup docs
   git mv QUICK-START.md docs/setup/quick-start.md
   git mv SETUP-guide.md docs/setup/installation.md
   git commit -m "refactor(docs): relocate setup docs to docs/setup/"
   ```

3. **Link updates**: Separate commit AFTER file moves
   ```bash
   # Commit 1: File moves
   git mv ... && git commit -m "refactor(docs): relocate files"

   # Commit 2: Link updates
   # Update links...
   git commit -m "refactor(docs): update links for relocated files"
   ```

### Rationale

- **git mv preserves history**: Git tracks renames via content similarity, preserves blame/log
- **Separate commits**: Makes history clearer (file structure change vs. content change)
- **--follow flag**: Ensures git log shows pre-move history

### Cases Where History Breaks

- **Edit + move in same commit**: Git may not detect rename if >50% content changed
- **Move + link update in same file**: If file both moves and has internal links updated, split operations
- **Mitigation**: Keep moves pure (no content edits), test with `git log --follow`

### Validation

After moves, verify history preservation:
```bash
git log --follow --oneline docs/setup/installation.md
# Should show commits from SETUP-guide.md era
```

---

## R4: Duplicate Detection Strategy

### Decision: Three-Tier Detection (Exact, Near-Exact, Semantic)

### Tier 1: Exact Duplicates

**Method**: File hash comparison
```bash
find docs/ -name "*.md" -type f -exec md5sum {} \; | sort | uniq -w32 -D
```

**Outcome**: List of files with identical content
**Action**: Delete all but one, update links to remaining file

### Tier 2: Near-Exact Duplicates (>80% similar)

**Method**: Manual review with diff
```bash
# Find candidates by similar filenames
find docs/ -name "*error*.md" | xargs -n2 diff -u
```

**Outcome**: Files with mostly similar content (different headers/formatting)
**Action**: Consolidate into single authoritative file, archive if historical value

### Tier 3: Semantic Duplicates (same topic, different content)

**Method**: Manual review by category
- List all files in category
- Review titles/purposes
- Identify overlapping coverage

**Outcome**: Multiple files about same topic (e.g., 7 error documentation files)
**Action**: Merge into comprehensive guide with subsections

### Rationale

- **Exact duplicates**: Automated detection is reliable and fast
- **Near-exact**: Requires human judgment (which version is canonical?)
- **Semantic**: Requires domain knowledge (are these truly duplicates or complementary?)

### Known Duplicate Candidates (from spec analysis)

1. **FEATURES.md vs. docs/features-overview.md**: Exact or near-exact
2. **docs/api/errors.md, ERRORS.md, errors-*.md (7 files)**: Semantic duplicates
3. **Root-level summaries** (IMPLEMENTATION-COMPLETION-summary.md, etc.): Historical artifacts, not duplicates

### Implementation Approach

- Phase 1: Run exact duplicate detection, resolve immediately
- Phase 2: Manually review semantic duplicate candidates per category
- Phase 3: Consolidate during relocation (merge content before moving)

---

## R5: Documentation Categorization Rules

### Decision Tree

```
START: Need to categorize documentation file

Q1: Is this about installing/configuring the system?
  YES → setup/
  NO → Q2

Q2: Is this about fixing problems or errors?
  YES → troubleshooting/
  NO → Q3

Q3: Is this API specification, endpoints, or models?
  YES → api/
  NO → Q4

Q4: Is this about system architecture or design decisions?
  YES → architecture/
  NO → Q5

Q5: Is this about development workflows, testing, or contributing?
  YES → development/
  NO → Q6

Q6: Is this describing a user-facing feature or capability?
  YES → features/
  NO → Q7

Q7: Is this a historical report, retrospective, or analysis artifact?
  YES → reports/
  NO → UNCLEAR (flag for manual review)
```

### Categorization Rules

#### 1. User-Facing vs. Developer Documentation

**User-facing** (setup/, troubleshooting/, features/):
- Describes WHAT system does or HOW to use it
- No code examples or internal architecture
- Goal: Enable operators/end-users

**Developer-facing** (api/, architecture/, development/):
- Describes HOW system works internally or HOW to build/extend it
- Includes code examples, design rationale, contribution guidelines
- Goal: Enable contributors/integrators

#### 2. Mixed-Audience Documents

For documents with both user and developer content:
- **Option A**: Split into separate files (preferred if >100 lines each)
- **Option B**: Keep unified with clear section headers:
  ```markdown
  ## For Users
  [User-facing content]

  ## For Developers
  [Developer-facing content]
  ```

**Categorization**: Place in category matching primary audience (>60% of content)

#### 3. Historical vs. Current Documentation

**Current** (active categories):
- Describes current state of system
- Maintained and updated with code changes
- Includes: all user guides, API docs, architecture docs

**Historical** (reports/):
- Describes past state or completed work
- Not updated (frozen at completion date)
- Includes: implementation summaries, retrospectives, analysis reports
- **Requirement**: Must include date in filename or frontmatter

#### 4. Temporary/WIP Documentation

**Rule**: No temporary documentation at root or in active categories

**Process**:
- WIP docs MUST be in personal branches, not main
- If must be in main, prefix with `TEMP-` and place in `docs/reports/temp/`
- TEMP- files MUST be cleaned up before merge or within 30 days

#### 5. Backend-Specific vs. Project-Wide

**Backend-specific** (keep in `backend/starlink-location/docs/`):
- Specific to starlink-location service implementation
- Not relevant to other services or frontend
- Examples: service-specific architecture, internal testing procedures

**Project-wide** (move to `docs/`):
- Relevant across services (frontend + backend)
- Describes system-level behavior or APIs
- Examples: user-facing setup, API contracts, feature descriptions

**Test**: "Would a frontend developer need this?" → YES means project-wide

### Example Categorizations

| File                              | Category         | Rationale                           |
| --------------------------------- | ---------------- | ----------------------------------- |
| QUICK-START.md                    | setup/           | Getting system running              |
| api-reference-index.md            | api/             | API specification                   |
| FEATURES.md                       | features/        | User-facing capabilities            |
| design-document.md                | architecture/    | System design                       |
| development-workflow.md           | development/     | Developer process                   |
| troubleshooting.md                | troubleshooting/ | Problem-solving                     |
| IMPLEMENTATION-COMPLETION-SUMMARY | reports/         | Historical artifact (dated)         |
| backend/.../ARCHITECTURE.md       | (keep in place)  | Backend-specific implementation     |
| docs/exporter/analysis/...        | reports/         | Feature implementation history      |

### Edge Cases

**Case**: Documentation about documentation structure (this file, data-model.md)
- **Category**: development/ (how to contribute to docs)
- **Alternative**: Meta-documentation in specs/ (keep with feature planning)

**Case**: Mission communication SOP (operational procedure with technical details)
- **Category**: features/ or setup/ (mixed audience, operational focus)
- **Split if needed**: setup/mission-sop.md (user guide) + development/mission-testing.md (developer guide)

---

## Research Summary

### Key Findings

1. **Documentation Taxonomy**: 7-category system based on Divio framework with project-specific adaptations
2. **Link Management**: Two-phase approach (discovery + validation) using ripgrep and markdown-link-check
3. **Git History**: Use `git mv` with proper commit structure preserves full history
4. **Duplicate Detection**: Three-tier strategy (exact, near-exact, semantic) with manual review for semantic duplicates
5. **Categorization**: Decision tree with clear user/developer split and historical vs. current distinction

### Unresolved Questions

None. All research tasks complete with actionable recommendations.

### Next Steps

Proceed to Phase 1: Design (data-model.md, contracts, quickstart.md)

---

**Research Status**: ✓ Complete
**Blockers**: None
**Ready for**: Phase 1 Design
