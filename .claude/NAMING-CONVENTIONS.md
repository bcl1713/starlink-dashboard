# File Naming Conventions

This document defines file naming standards for the starlink-dashboard-dev project to ensure consistency across documentation, task management files, and session tracking.

## Core Principle

**Use hyphens (-) not underscores (_) for multi-word filenames.**

Hyphens are:
- Easier to type (no shift key required)
- More readable in file listings
- Standard convention in modern development
- URL-friendly

## File Naming Categories

### 1. Status and Session Files (High Visibility)

**Convention:** ALL CAPS with hyphens

These files need to stand out in directory listings for quick visibility.

**Examples:**
- `SESSION-NOTES.md` ✅
- `CONTEXT-HANDOFF.md` ✅
- `PHASE-3-SUMMARY.md` ✅
- `STATUS.md` ✅
- `README.md` ✅ (standard convention)

**Anti-patterns:**
- `session_notes.md` ❌ (lowercase with underscores)
- `SESSION_NOTES.md` ❌ (underscores instead of hyphens)
- `SessionNotes.md` ❌ (PascalCase)

**When to use:**
- Session tracking files
- Project status files
- Phase summaries
- Context handoff documents
- README files at any level

---

### 2. Task Planning Files (Descriptive Names)

**Convention:** kebab-case (lowercase with hyphens)

These files describe specific features, tasks, or components.

**Examples:**
- `poi-interactive-management-plan.md` ✅
- `grafana-dashboard-context.md` ✅
- `authentication-refactor-tasks.md` ✅
- `api-integration-notes.md` ✅

**Anti-patterns:**
- `poi_interactive_management_plan.md` ❌ (underscores)
- `POI-Interactive-Management-Plan.md` ❌ (mixed case)
- `poiInteractiveManagementPlan.md` ❌ (camelCase)

**When to use:**
- Task planning files (`[task-name]-plan.md`)
- Context files (`[task-name]-context.md`)
- Task tracking files (`[task-name]-tasks.md`)
- Feature-specific documentation

---

### 3. Project Documentation Files

**Convention:** ALL CAPS with hyphens (for major docs)

**Examples:**
- `IMPLEMENTATION-SUMMARY.md` ✅
- `FINAL-VERIFICATION-REPORT.md` ✅
- `TROUBLESHOOTING.md` ✅
- `BEST-PRACTICES.md` ✅

**Anti-patterns:**
- `IMPLEMENTATION_SUMMARY.md` ❌ (underscores)
- `implementation-summary.md` ❌ (lowercase for major docs)

**When to use:**
- Top-level project documentation
- Major summary/report files
- Project-wide reference guides

---

### 4. Technical Documentation Files

**Convention:** kebab-case

**Examples:**
- `api-reference.md` ✅
- `data-flow-diagram.md` ✅
- `deployment-guide.md` ✅
- `testing-strategy.md` ✅

**When to use:**
- API documentation
- Technical guides
- Architecture documentation
- Component-specific docs

---

## Naming Patterns by Tool

### `/dev-docs` Command Output

Creates files in `dev/active/[task-name]/`:

```
poi-interactive-management/
├── README.md                              (ALL CAPS - standard)
├── poi-interactive-management-plan.md     (kebab-case - descriptive)
├── poi-interactive-management-context.md  (kebab-case - descriptive)
└── poi-interactive-management-tasks.md    (kebab-case - descriptive)
```

### `/dev-docs-update` Command Output

Creates session files in `dev/active/[task-name]/`:

```
SESSION-NOTES.md           (ALL CAPS - high visibility)
CONTEXT-HANDOFF.md         (ALL CAPS - high visibility)
PHASE-N-SUMMARY.md         (ALL CAPS - high visibility)
```

### `documentation-architect` Agent Output

- Status/overview docs: ALL CAPS with hyphens
- Technical docs: kebab-case
- README files: `README.md`

---

## Quick Reference Table

| File Type | Convention | Example |
|-----------|-----------|---------|
| Session tracking | ALL CAPS + hyphens | `SESSION-NOTES.md` |
| Status files | ALL CAPS + hyphens | `STATUS.md` |
| Phase summaries | ALL CAPS + hyphens | `PHASE-3-SUMMARY.md` |
| Task planning | kebab-case | `feature-name-plan.md` |
| Task context | kebab-case | `feature-name-context.md` |
| Task tracking | kebab-case | `feature-name-tasks.md` |
| Project docs | ALL CAPS + hyphens | `IMPLEMENTATION-SUMMARY.md` |
| Technical docs | kebab-case | `api-reference.md` |
| README files | `README.md` | `README.md` |

---

## Examples from Real Usage

### Good Examples ✅

From `/dev/active/poi-interactive-management/`:
```
SESSION-NOTES.md
CONTEXT-HANDOFF.md
PHASE-3-COMPLETION.md
poi-interactive-management-plan.md
poi-interactive-management-context.md
poi-interactive-management-tasks.md
poi-best-practices-research.md
```

### Bad Examples ❌

These violate the conventions:
```
PANEL_TYPES.md              → should be PANEL-TYPES.md
IMPLEMENTATION_SUMMARY.md   → should be IMPLEMENTATION-SUMMARY.md
session_notes.md            → should be SESSION-NOTES.md
taskName.md                 → should be task-name.md
```

---

## Why These Conventions?

### Readability
- Hyphens are easier to read than underscores
- ALL CAPS files stand out in directory listings
- kebab-case is clean and modern

### Consistency
- Reduces decision fatigue ("how should I name this?")
- Makes it easy to find related files
- Creates predictable patterns

### Cross-Platform
- Works on all operating systems
- URL-friendly (important for documentation sites)
- No issues with case-insensitive filesystems

### Developer Experience
- Faster to type (hyphens don't require shift key)
- Easier to select (double-click selects whole filename)
- Standard convention in modern tooling

---

## Enforcement

All slash commands, agents, and tools should follow these conventions when creating files. New contributors should reference this guide when creating documentation or task management files.

---

**Last Updated:** 2025-10-31
