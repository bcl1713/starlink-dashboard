# Documentation Structure Quick Start

**Audience**: Contributors adding or updating documentation **Last Updated**:
2025-12-04 **Purpose**: Quick reference for navigating and contributing to
Starlink Dashboard documentation

---

## Finding Documentation

### By Purpose

| I need to...                    | Look in...                                                       |
| ------------------------------- | ---------------------------------------------------------------- |
| Install or configure the system | [docs/setup/](../../../docs/setup/README.md)                     |
| Fix a problem or error          | [docs/troubleshooting/](../../../docs/troubleshooting/README.md) |
| Understand an API endpoint      | [docs/api/](../../../docs/api/README.md)                         |
| Learn about a feature           | [docs/features/](../../../docs/features/README.md)               |
| Understand system architecture  | [docs/architecture/](../../../docs/architecture/README.md)       |
| Contribute or run tests         | [docs/development/](../../../docs/development/README.md)         |
| Find historical reports         | [docs/reports/](../../../docs/reports/README.md)                 |

### By Audience

**Users/Operators**:

- Setup: [docs/setup/](../../../docs/setup/README.md)
- Features: [docs/features/](../../../docs/features/README.md)
- Troubleshooting:
  [docs/troubleshooting/](../../../docs/troubleshooting/README.md)

**Developers/Contributors**:

- Development: [docs/development/](../../../docs/development/README.md)
- Architecture: [docs/architecture/](../../../docs/architecture/README.md)
- API: [docs/api/](../../../docs/api/README.md)

**API Consumers/Integrators**:

- API Reference: [docs/api/](../../../docs/api/README.md)
- Examples: [docs/api/examples/](../../../docs/api/examples/README.md)

---

## Adding New Documentation

### Decision Flowchart

```
Q1: Is this about installing/configuring?
    YES → docs/setup/[your-doc].md
    NO → Q2

Q2: Is this about fixing problems?
    YES → docs/troubleshooting/[your-doc].md
    NO → Q3

Q3: Is this API specification/reference?
    YES → docs/api/[subcategory]/[your-doc].md
    NO → Q4

Q4: Is this about system architecture?
    YES → docs/architecture/[your-doc].md
    NO → Q5

Q5: Is this about development workflows?
    YES → docs/development/[your-doc].md
    NO → Q6

Q6: Is this describing a feature?
    YES → docs/features/[your-doc].md
    NO → Q7

Q7: Is this a historical report/retrospective?
    YES → docs/reports/[your-doc].md
    NO → Ask for guidance in PR or issue
```

### Quick Rules

1. **Name your file**: Use `lowercase-with-hyphens.md` format
2. **Check category README**: See if your topic fits existing structure
3. **Create in right category**: Use flowchart above
4. **Update category README**: Add your doc to the category's README.md
5. **Use relative links**: Link to other docs with `../category/file.md`
6. **Keep it short**: Aim for <300 lines; split if needed

---

## Updating Documentation

### When a Feature Changes

1. **Find affected docs**: Search for feature name across docs/

   ```bash
   rg "feature name" docs/
   ```

2. **Update relevant files**:
   - API docs: [docs/api/](../../../docs/api/README.md)
   - Feature description: [docs/features/](../../../docs/features/README.md)
   - Setup if configuration changed:
     [docs/setup/](../../../docs/setup/README.md)

3. **Test links**: Verify links still work after updates

### When Moving Documentation

**IMPORTANT**: Follow these steps to preserve git history and avoid broken
links.

1. **Use git mv** (preserves history):

   ```bash
   git mv old/location.md new/location.md
   ```

2. **Update links IN moved file** (recalculate relative paths from new location)

3. **Update links TO moved file** (find all docs linking to it):

   ```bash
   rg 'old/location\.md' docs/
   # Update each found link
   ```

4. **Commit file move + link updates together**:

   ```bash
   git commit -m "refactor(docs): relocate location.md

   - Move from old/ to new/
   - Update all internal and external links
   "
   ```

5. **Validate links**:
   ```bash
   # See "Validating Links" section below
   ```

---

## Documentation Standards

### File Format

**Required**:

- Top-level heading (H1): Clear title
- Lowercase-with-hyphens filename
- Relative links to other docs

**Recommended**:

- Purpose statement (for docs >100 lines)
- Table of contents (for docs >200 lines)
- Last updated date

**Example**:

```markdown
# Setup Guide

**Purpose**: Help users install and configure Starlink Dashboard **Last
Updated**: 2025-12-04

## Prerequisites

[Content...]

## Installation

[Content...]

## Related Documentation

- [Troubleshooting](../troubleshooting/README.md)
- [Configuration](./configuration.md)
```

### Link Format

**Always use relative paths**:

```markdown
<!-- Good -->

[API Reference](../api/README.md) [Setup Guide](../../setup/installation.md)
[Section in this file](#installation)

<!-- Bad -->

[API Reference](/docs/api/README.md) # Absolute path
[Setup Guide](docs/setup/installation.md) # Root-relative
```

**Anchor links**: Use lowercase-with-hyphens matching heading text

- Heading: "## Installation Steps"
- Anchor: `#installation-steps`

### File Size

**Target**: ≤300 lines per file (Constitution Principle IV)

**If your doc exceeds 300 lines**:

- Split by subtopic: `api-reference.md` → `api-endpoints.md`, `api-models.md`
- Split by progression: `setup.md` → `setup-install.md`, `setup-configure.md`
- Split by audience: `guide.md` → `user-guide.md`, `developer-guide.md`

---

## Category Structure Rules

### Top-Level Files

**Limit**: <15 markdown files per category (excluding README.md)

**If you have >15 files**: Use subcategories

```
docs/api/
├── README.md        # Category index
├── endpoints/       # Subcategory
│   ├── README.md
│   ├── missions.md
│   └── pois.md
├── models/
│   ├── README.md
│   └── ...
```

### Category README.md

**Every category MUST have README.md** with:

- Category purpose
- Primary audience
- List of documentation in category
- Links to related categories

**Template**:

```markdown
# [Category Name]

**Purpose**: [One sentence] **Audience**: [Primary readers]

## Documentation in This Category

### [Subtopic]

- **[Doc Title]**: [One-sentence description]
- **[Doc Title]**: [One-sentence description]

## Related Documentation

- [Related Category](../category/README.md)
```

---

## Validating Links

### Before Committing

**Manual check**: Open your documentation in markdown preview, click all links.

**Automated check** (if markdown-link-check installed):

```bash
markdown-link-check docs/your-category/your-doc.md
```

### Before Merging

**Comprehensive validation**:

```bash
# Check all documentation links
find docs/ -name "*.md" -type f | while read file; do
  markdown-link-check "$file" || echo "FAILED: $file"
done
```

**Install markdown-link-check**:

```bash
npm install -g markdown-link-check
```

### Common Issues

**Broken relative link**: Recalculate path from source file location

- From: `docs/setup/installation.md`
- To: `docs/api/README.md`
- Link: `../api/README.md` (up one level, then down to api/)

**Broken anchor link**: Verify heading exists in target file

- Check heading text matches anchor (lowercase-with-hyphens)
- Example: "## API Reference" → `#api-reference`

---

## Root-Level Documentation

**ONLY these files allowed at repository root**:

- `README.md` - Project overview
- `CLAUDE.md` - Runtime guidance for AI
- `AGENTS.md` - Agent configuration
- `CONTRIBUTING.md` - Contribution guidelines

**All other documentation MUST be in**:

- `docs/` - Project-wide documentation
- `backend/*/docs/` - Service-specific documentation
- `specs/` - Feature specifications

**No temporary files at root**: Use `docs/reports/temp/` if must be in main
branch.

---

## Backend-Specific Documentation

**Question**: Is this specific to ONE service's implementation?

**YES** → Keep in `backend/[service]/docs/`

- Examples: Backend service architecture, backend-specific testing, internal
  implementation details

**NO** → Move to `docs/`

- Examples: API specifications, user-facing features, project-wide setup

**Test**: "Would a frontend developer need this?" → YES means `docs/`

---

## Common Tasks

### Add API Documentation

1. **Endpoint docs**: `docs/api/endpoints/[feature].md`
2. **Model docs**: `docs/api/models/[feature]-models.md`
3. **Examples**: `docs/api/examples/[language]-examples.md`
4. **Update index**: Add links to `docs/api/README.md`

### Add Feature Documentation

1. **Feature overview**: `docs/features/[feature-name].md`
2. **Setup (if needed)**: `docs/setup/[feature-name]-setup.md`
3. **Update indexes**: `docs/features/README.md`, `docs/index.md`

### Add Troubleshooting Guide

1. **By service**: `docs/troubleshooting/services/[service-name].md`
2. **By symptom**: `docs/troubleshooting/[symptom-type].md`
3. **Update index**: `docs/troubleshooting/README.md`

### Create Historical Report

1. **Add to reports**: `docs/reports/YYYY-MM-DD-[report-name].md`
2. **Include date and status**: In filename or frontmatter
3. **Mark as complete**: "Status: COMPLETE" or "ARCHIVED"
4. **Update index**: `docs/reports/README.md`

---

## Getting Help

### Documentation Questions

- **Structure unclear**: Review [data-model.md](./data-model.md) for complete
  taxonomy
- **Contract requirements**: See [contracts/](./contracts/) for detailed rules
- **Link validation**: See
  [link-validation-checklist.md](./contracts/link-validation-checklist.md)

### Contribution Questions

- **General contribution guidelines**:
  [CONTRIBUTING.md](../../../CONTRIBUTING.md)
- **Development workflow**:
  [docs/development/workflow.md](../../../docs/development-workflow.md)
- **Code quality standards**:
  [.specify/memory/constitution.md](../../../.specify/memory/constitution.md)

---

## Quick Reference

### File Naming

```bash
✓ quick-start.md
✓ api-reference.md
✗ QuickStart.md
✗ API_Reference.md
```

### Links

```markdown
✓ [Setup](../setup/installation.md) ✓ [API](../../api/README.md) ✗
[Setup](/docs/setup/installation.md)
```

### File Size

```
✓ ≤300 lines
⚠ >300 lines with justification
✗ >300 lines without justification
```

### Root Level

```
✓ README.md, CLAUDE.md, AGENTS.md, CONTRIBUTING.md
✗ Any other .md files
```

---

**Quick Start Status**: ✓ Complete **For More Details**: See
[data-model.md](./data-model.md) and [contracts/](./contracts/)
