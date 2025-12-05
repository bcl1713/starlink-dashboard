# Link Validation Contract

**Feature**: Documentation Cleanup and Restructuring
**Date**: 2025-12-04
**Purpose**: Define requirements and procedures for validating documentation links

---

## Link Requirements

### R1: Relative Paths Only

**Requirement**: All internal markdown links MUST use relative paths.

**Allowed**:
```markdown
[Setup Guide](../setup/installation.md)
[API Reference](../../api/README.md)
[Section](#authentication)
```

**Prohibited**:
```markdown
[Setup Guide](/docs/setup/installation.md)        # Absolute path
[Setup Guide](docs/setup/installation.md)         # Root-relative path
[API Docs](http://localhost/docs/api/README.md)   # URL
```

**Rationale**:
- Relative paths work regardless of repository location
- Portable across forks and local clones
- Compatible with markdown renderers

### R2: Link Format

**Standard markdown links**:
```markdown
[Link Text](path/to/file.md)
[Link with Anchor](path/to/file.md#section-heading)
```

**Anchor format rules**:
- Lowercase only
- Spaces replaced with hyphens
- Special characters removed
- Example: "API v2.0 Reference" → `#api-v20-reference`

### R3: Link Targets Must Exist

**Requirement**: All link targets MUST be valid files or anchors.

**Valid**:
- Link points to existing .md file
- Anchor points to existing heading in target file
- External links (http/https) respond with 200 OK (optional check)

**Invalid**:
- Link points to non-existent file
- Anchor points to non-existent heading
- Broken external links (optional check)

---

## Validation Workflow

### Phase 1: Pre-Move Link Discovery

**Objective**: Identify all links before file moves to plan updates.

**Steps**:

1. **Find all markdown links**:
   ```bash
   rg '\[.*\]\((.*\.md[^)]*)\)' --only-matching --no-filename docs/ > links-inventory.txt
   ```

2. **Extract link components**:
   ```bash
   # Parse links into: source_file | link_text | target_path | anchor
   rg '\[([^\]]+)\]\(([^)]+)\)' --replace '$1 | $2' docs/ > links-parsed.txt
   ```

3. **Categorize links**:
   - Internal relative links (need updating)
   - Internal absolute links (need conversion)
   - External links (no update needed)
   - Anchor-only links (verify after moves)

**Output**: `links-inventory.txt`, `links-parsed.txt` for reference during moves

---

### Phase 2: Link Updates During Moves

**Objective**: Update links atomically with file moves.

**Workflow**:

1. **Move file with git mv**:
   ```bash
   git mv old/location/file.md new/location/file.md
   ```

2. **Update links in moved file**:
   - Recalculate relative paths from new location
   - Update all links to other docs/
   - Test: Open file in markdown preview, click links

3. **Update links TO moved file**:
   ```bash
   # Find all files linking to moved file
   rg 'old/location/file\.md' docs/
   # Update each found link to new/location/file.md
   ```

4. **Commit file move + link updates together**:
   ```bash
   git commit -m "refactor(docs): relocate file.md to new location

   - Move file.md from old/location to new/location
   - Update all internal links in file.md
   - Update all links to file.md from other docs
   "
   ```

**Critical**: File move and link updates MUST be in same commit to avoid broken link states.

---

### Phase 3: Post-Move Validation

**Objective**: Verify all links work after reorganization complete.

**Method 1: Automated (markdown-link-check)**

```bash
# Install markdown-link-check (if not present)
npm install -g markdown-link-check

# Check all markdown files
find docs/ -name "*.md" -type f | while read file; do
  echo "Checking $file..."
  markdown-link-check "$file" || echo "FAILED: $file"
done
```

**Pass criteria**:
- All files pass markdown-link-check
- No 404 errors for relative links
- Anchors resolve correctly

**Method 2: Manual Script**

```bash
#!/bin/bash
# link-validator.sh

find docs/ -name "*.md" | while read source_file; do
  # Extract links
  rg '\]\(([^)]+\.md[^)]*)\)' --only-matching "$source_file" | \
  sed 's/.*(\(.*\))/\1/' | \
  while read link; do
    # Remove anchor
    target=$(echo "$link" | sed 's/#.*//')

    # Resolve relative path
    source_dir=$(dirname "$source_file")
    resolved_target="$source_dir/$target"

    # Normalize path (remove ../ and ./)
    resolved_target=$(realpath --relative-to=. "$resolved_target" 2>/dev/null)

    # Check target exists
    if [[ ! -f "$resolved_target" ]]; then
      echo "BROKEN: $source_file -> $link (resolves to $resolved_target)"
    fi
  done
done
```

**Pass criteria**:
- Script exits with 0 (no broken links found)
- All relative links resolve to existing files

---

## Link Update Strategies

### Strategy 1: Category-Level Moves (Preferred)

Move entire categories at once and update links in batches:

```bash
# Example: Move all setup docs
git mv QUICK-START.md docs/setup/quick-start.md
git mv SETUP-GUIDE.md docs/setup/installation.md

# Update all links in one pass
find docs/ -name "*.md" -exec sed -i 's|QUICK-START\.md|../setup/quick-start.md|g' {} \;
find docs/ -name "*.md" -exec sed -i 's|SETUP-GUIDE\.md|../setup/installation.md|g' {} \;

git commit -m "refactor(docs): relocate setup documentation"
```

**Pros**: Fewer commits, easier to track related moves
**Cons**: Larger commits, harder to review

---

### Strategy 2: File-by-File Moves (Safer)

Move files individually with immediate link updates:

```bash
# Move one file
git mv QUICK-START.md docs/setup/quick-start.md

# Update links immediately
find docs/ -name "*.md" -exec sed -i 's|QUICK-START\.md|../setup/quick-start.md|g' {} \;

git commit -m "refactor(docs): relocate QUICK-START.md to docs/setup/"

# Repeat for next file...
```

**Pros**: Easier to review, atomic changes, safer rollback
**Cons**: More commits, slower process

**Recommendation**: Use Strategy 2 for critical files, Strategy 1 for bulk category moves.

---

## Edge Cases

### Case 1: Links in Code Comments

**Detection**:
```bash
rg '\[.*\]\(.*\.md.*\)' --type py --type js --type ts
```

**Handling**: Out of scope per spec assumptions, but flag for follow-up.

### Case 2: Anchor Links to Moved Files

**Challenge**: Anchors may be to old headers that no longer exist after consolidation.

**Verification**:
```bash
# Check anchor links
rg '\]\([^)]*\.md#([^)]+)\)' docs/ | \
  # Extract target file and anchor
  # Verify heading exists in target file
```

**Manual review required**: Automated tools may not validate anchors correctly.

### Case 3: External Links

**Handling**: No updates needed, but optional validation:
```bash
# Find external links
rg '\]\(https?://[^)]+\)' docs/

# Optional: Test reachability
curl -I [url] | grep "200 OK"
```

**Recommendation**: External link validation is optional and out of primary scope.

### Case 4: README Links from Root

Special case: README.md at root links to docs/

**Requirement**: Update README.md links when docs/ structure changes.

**Example**:
```markdown
<!-- Before -->
[Quick Start](./docs/QUICK-START.md)

<!-- After -->
[Quick Start](./docs/setup/quick-start.md)
```

**Critical**: README.md is entry point; broken links harm first impressions.

---

## Validation Checklist

Use this checklist before merging documentation reorganization:

### Pre-Merge Validation

- [ ] All markdown files validated with markdown-link-check OR manual script
- [ ] No broken internal links (files exist)
- [ ] No broken anchor links (headings exist)
- [ ] README.md links updated and verified
- [ ] All links use relative paths (no absolute or root-relative)
- [ ] Links updated atomically with file moves (same commits)

### Spot Check (Manual)

- [ ] Navigate from README.md to 3 random docs (links work)
- [ ] Navigate from docs/INDEX.md to 5 random category indexes (links work)
- [ ] Open 5 random documentation files, click all internal links (work)
- [ ] Test anchor links to sections within files (3 random examples)

### Git History Verification

- [ ] Moved files preserve history (`git log --follow [file]` shows pre-move commits)
- [ ] File move commits include link updates (atomic changes)
- [ ] No "fix broken links" commits after moves (should be atomic)

---

## Tools Reference

### Recommended Tools

1. **markdown-link-check** (npm)
   - Automated link validation
   - Handles relative paths and anchors
   - Exit codes for CI integration
   - Install: `npm install -g markdown-link-check`

2. **ripgrep (rg)**
   - Fast pattern matching for link discovery
   - Pre-installed in most development environments
   - Used throughout validation workflow

3. **realpath** (coreutils)
   - Resolve relative paths to absolute paths
   - Useful for manual validation scripts
   - Pre-installed on Linux/macOS

### Optional Tools

1. **linkchecker** (Python)
   - More comprehensive, includes external link checking
   - Heavier dependency (Python + libraries)
   - Overkill for internal-only link validation

2. **markdown-link-validator** (Rust)
   - Fast alternative to markdown-link-check
   - Fewer features, simpler use case

**Recommendation**: Start with markdown-link-check, fall back to manual script if issues arise.

---

## Automation Script (Reference Implementation)

```bash
#!/bin/bash
# validate-docs-links.sh
# Usage: ./validate-docs-links.sh

set -euo pipefail

echo "=== Documentation Link Validation ==="
echo

errors=0

# Check 1: Find all markdown files
echo "Finding markdown files..."
md_files=$(find docs/ README.md CONTRIBUTING.md -name "*.md" -type f 2>/dev/null)
file_count=$(echo "$md_files" | wc -l)
echo "Found $file_count markdown files"
echo

# Check 2: Validate links with markdown-link-check
if command -v markdown-link-check &> /dev/null; then
  echo "Running markdown-link-check..."
  echo "$md_files" | while read file; do
    if ! markdown-link-check "$file" --quiet; then
      echo "FAILED: $file"
      ((errors++))
    fi
  done
else
  echo "WARNING: markdown-link-check not installed, skipping automated check"
  echo "Install with: npm install -g markdown-link-check"
fi

echo

# Check 3: Verify relative paths
echo "Checking for absolute paths (should be relative)..."
absolute_links=$(rg '\]\(/docs/' docs/ README.md || true)
if [[ -n "$absolute_links" ]]; then
  echo "VIOLATION: Found absolute paths (should be relative):"
  echo "$absolute_links"
  ((errors++))
else
  echo "✓ All links use relative paths"
fi

echo

# Summary
if [[ $errors -eq 0 ]]; then
  echo "=== ✓ All Validation Checks Passed ==="
  exit 0
else
  echo "=== ✗ Validation Failed with $errors errors ==="
  exit 1
fi
```

**Usage**: Run before merging documentation changes.

---

**Link Validation Contract Status**: ✓ Defined
**Automation**: Validation script provided
**Enforcement**: MUST pass before merge
