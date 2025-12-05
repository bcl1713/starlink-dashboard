# Documentation Category Requirements Contract

**Feature**: Documentation Cleanup and Restructuring
**Date**: 2025-12-04
**Purpose**: Define testable requirements for documentation organization

---

## Contract 1: Category Index Requirements

### Requirement

Every top-level documentation category MUST have a `README.md` index file.

### Verification

```bash
# Check all categories have README.md
for category in setup api features troubleshooting architecture development reports; do
  [[ -f "docs/$category/README.md" ]] || echo "MISSING: docs/$category/README.md"
done
```

### Pass Criteria

- Exit code 0 (no missing README.md files)
- All category directories contain README.md

### README.md Content Requirements

Each category README.md MUST include:
1. **Category heading** (H1): Name of the category
2. **Purpose statement**: One-sentence description of category purpose
3. **Audience statement**: Primary reader types
4. **Documentation list**: All files in category with brief descriptions
5. **Related documentation links**: Links to related categories (optional)

### Example

```markdown
# API Reference

**Purpose**: Technical reference for REST API endpoints, models, and contracts
**Audience**: API consumers, integrators, developers

## Documentation in This Category

### Endpoints

- **Core Endpoints**: Health, status, and metrics endpoints
- **Mission Endpoints**: Mission creation and management APIs

## Related Documentation

- [Features](../features/README.md) - Capability descriptions using these APIs
- [Setup](../setup/README.md) - API configuration and authentication setup
```

---

## Contract 2: File Count Limits

### Requirement

Top-level categories MUST contain fewer than 15 files. Categories with >15 files MUST use subcategories.

### Verification

```bash
# Check file counts per category
for category in setup api features troubleshooting architecture development reports; do
  count=$(find "docs/$category" -maxdepth 1 -name "*.md" -not -name "README.md" | wc -l)
  if [[ $count -ge 15 ]]; then
    echo "VIOLATION: docs/$category has $count files (limit: 14)"
  fi
done
```

### Pass Criteria

- All categories have <15 markdown files at top level (excluding README.md)
- Categories with many files use subdirectories

### Rationale

- Flat directories with >15 files become difficult to navigate
- Subcategories provide logical grouping and improve discoverability
- Preserves usability of file explorers and directory listings

---

## Contract 3: Root-Level Restriction

### Requirement

ONLY the following markdown files are allowed at repository root:
- `README.md` - Project overview
- `CLAUDE.md` - Runtime guidance
- `AGENTS.md` - Agent configuration
- `CONTRIBUTING.md` - Contribution guidelines

ALL other markdown documentation MUST be in:
- `docs/` - Project-wide documentation
- `backend/*/docs/` - Service-specific documentation
- `specs/` - Feature specifications and planning

### Verification

```bash
# Find unauthorized root-level markdown files
find . -maxdepth 1 -name "*.md" -type f \
  -not -name "README.md" \
  -not -name "CLAUDE.md" \
  -not -name "AGENTS.md" \
  -not -name "CONTRIBUTING.md" \
  | while read file; do
      echo "VIOLATION: $file should be in docs/, backend/*/docs/, or specs/"
    done
```

### Pass Criteria

- Exit code 0 (no unauthorized root-level markdown files)
- Only 4 allowed markdown files at root

### Rationale

- Reduces root-level clutter
- Establishes docs/ as the canonical documentation location
- Makes documentation structure immediately clear to new contributors

---

## Contract 4: Duplicate Prevention

### Requirement

No two documentation files MUST contain identical or substantially similar content. Semantic duplicates (multiple files about the same topic) MUST be consolidated into single authoritative sources.

### Verification (Exact Duplicates)

```bash
# Find files with identical content
find docs/ -name "*.md" -type f -exec md5sum {} \; \
  | sort | uniq -w32 -D \
  | awk '{print $2}' \
  | while read file; do
      echo "EXACT DUPLICATE: $file"
    done
```

### Verification (Semantic Duplicates - Manual)

Manual review process:
1. List all files in each category
2. Identify files with overlapping topics (same keywords in names)
3. Review content for substantial overlap (>50% similar coverage)
4. Consolidate or clearly differentiate

### Pass Criteria (Exact)

- Exit code 0 (no files with identical md5 hashes)

### Pass Criteria (Semantic)

- Manual review confirms no multiple files covering same topic
- Related topics clearly differentiated (different angles, audiences, or depth)

### Examples of Violations

**Exact Duplicate**:
- `docs/FEATURES.md` and `docs/features/FEATURES-OVERVIEW.md` containing identical text

**Semantic Duplicate**:
- `docs/api/errors.md`, `docs/api/ERRORS.md`, `docs/api/errors-format.md`, `docs/api/errors-handling.md` all describing API error responses

### Consolidation Requirements

When consolidating duplicates:
1. **Choose canonical location** using taxonomy rules
2. **Merge content** if complementary (preserve unique information)
3. **Update all links** to point to canonical location
4. **Archive historical versions** in reports/ if needed for context
5. **Delete duplicates** from active documentation

---

## Contract 5: Naming Conventions

### Requirement

All documentation files MUST follow lowercase-with-hyphens naming convention, except for established uppercase conventions.

### Verification

```bash
# Find files violating naming convention (except allowed uppercase)
find docs/ -name "*.md" -type f \
  -not -name "README.md" \
  -not -name "LICENSE.md" \
  | rg '[A-Z]' \
  | while read file; do
      echo "NAMING VIOLATION: $file (use lowercase-with-hyphens)"
    done
```

### Pass Criteria

- All files use lowercase letters and hyphens
- No files with camelCase, PascalCase, or SCREAMING_CASE (except README.md)

### Allowed Patterns

- **Correct**: `quick-start.md`, `api-reference.md`, `mission-planning.md`
- **Incorrect**: `QuickStart.md`, `APIReference.md`, `mission_planning.md`

### Exceptions

- `README.md` (uppercase by universal convention)
- `LICENSE.md` (if present, uppercase by convention)
- `CONTRIBUTING.md` (uppercase by convention, at root only)

---

## Contract 6: File Size Compliance

### Requirement

Documentation files MUST not exceed 300 lines, per Constitution Principle IV. Files exceeding 300 lines MUST be split or include justification comment.

### Verification

```bash
# Find files exceeding 300 lines
find docs/ -name "*.md" -type f \
  | while read file; do
      lines=$(wc -l < "$file")
      if [[ $lines -gt 300 ]]; then
        echo "SIZE VIOLATION: $file ($lines lines, limit: 300)"
      fi
    done
```

### Pass Criteria

- All files ≤300 lines OR
- Files >300 lines include justification comment at top

### Justification Format

For files legitimately >300 lines:
```markdown
<!--
  File Size Justification:
  This file exceeds 300 lines because [specific reason].
  Splitting considered but rejected because [reason].
  Planned split: [timeline or conditions], or N/A if permanent.
-->
```

### Splitting Guidance

Refer to data-model.md "Splitting Strategies" for approaches to reduce file size.

---

## Contract 7: Historical Document Requirements

### Requirement

All files in `docs/reports/` MUST include creation/completion date and status indicator.

### Verification (Manual)

For each file in `docs/reports/`:
1. Check filename includes date: `YYYY-MM-DD-description.md` OR
2. Check frontmatter includes `date:` field OR
3. Check document body includes clear completion date

### Pass Criteria

- 100% of reports/ files have identifiable dates
- 100% of reports/ files have status indicator (COMPLETE, ARCHIVED, or similar)

### Date Formats

**Filename** (preferred):
```
2025-12-04-implementation-summary.md
2025-11-15-retrospective.md
```

**Frontmatter** (alternative):
```markdown
---
date: 2025-12-04
status: COMPLETE
---
```

**Body text** (fallback):
```markdown
**Completed**: 2025-12-04
**Status**: ARCHIVED
```

---

## Contract 8: Backend-Specific Documentation Separation

### Requirement

Documentation specific to backend service implementation MUST remain in `backend/*/docs/`. Only project-wide documentation MUST be in `docs/`.

### Test Question

"Would a frontend developer or another service need this documentation?"
- **YES** → Project-wide, belongs in docs/
- **NO** → Service-specific, remains in backend/*/docs/

### Examples

**Project-wide** (docs/):
- API endpoint specifications
- User-facing feature descriptions
- System-wide setup and troubleshooting
- Architecture overview

**Backend-specific** (backend/starlink-location/docs/):
- Internal service architecture details
- Backend-specific testing procedures
- Service-specific troubleshooting (not visible to other services)
- Implementation-specific design decisions

### Verification (Manual)

Review backend/*/docs/ files and confirm:
- Each file describes implementation-specific detail
- No files describe user-facing behavior or APIs consumed by other services
- If project-wide content found, relocate to docs/

---

## Contract 9: Temporary Documentation Handling

### Requirement

No temporary or work-in-progress documentation is allowed in active categories or at repository root.

### Rules

1. **WIP docs** MUST be in personal feature branches, not main
2. **If WIP must be in main**: Prefix with `TEMP-` and place in `docs/reports/temp/`
3. **TEMP- files** MUST be cleaned up before merge or within 30 days
4. **No TEMP- files** allowed at repository root

### Verification

```bash
# Find temporary documentation
find . -name "TEMP-*.md" -o -name "WIP-*.md" -o -name "*-DRAFT.md" \
  | while read file; do
      if [[ ! "$file" =~ ^./docs/reports/temp/ ]]; then
        echo "VIOLATION: $file must be in docs/reports/temp/ or deleted"
      fi
    done
```

### Pass Criteria

- No TEMP-, WIP-, or DRAFT files outside docs/reports/temp/
- All TEMP- files have associated issue or cleanup date

---

## Summary: Contract Checklist

Use this checklist to verify documentation organization compliance:

- [ ] All categories have README.md index (Contract 1)
- [ ] All categories have <15 top-level files (Contract 2)
- [ ] Only 4 markdown files at repository root (Contract 3)
- [ ] No duplicate documentation (exact or semantic) (Contract 4)
- [ ] All files use lowercase-with-hyphens naming (Contract 5)
- [ ] All files ≤300 lines or justified (Contract 6)
- [ ] All reports/ files have dates and status (Contract 7)
- [ ] Backend-specific docs in correct location (Contract 8)
- [ ] No temporary docs in active categories (Contract 9)

**Enforcement**: These contracts MUST be verified before merging documentation changes.

---

**Contract Status**: ✓ Defined
**Automation**: Contracts 1-6, 9 have automated verification scripts
**Manual Review**: Contracts 4 (semantic), 7, 8 require manual verification
