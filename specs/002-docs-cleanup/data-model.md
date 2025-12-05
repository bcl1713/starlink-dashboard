# Phase 1: Documentation Taxonomy

**Feature**: Documentation Cleanup and Restructuring
**Date**: 2025-12-04
**Status**: Complete

## Overview

This document defines the complete taxonomy for organizing Starlink Dashboard documentation. It establishes categories, classification rules, naming conventions, and cross-reference strategies.

---

## Category Definitions

### 1. setup/

**Purpose**: Help users install, configure, and initially deploy the system
**Audience**: Users, operators, first-time installers
**Divio Type**: Tutorial (learning-oriented)

**Scope**:
- Initial installation procedures
- Configuration and environment setup
- Prerequisites and system requirements
- First-time deployment guides
- Quick start guides

**Out of Scope**:
- Troubleshooting (→ troubleshooting/)
- Development setup (→ development/)
- Architecture explanations (→ architecture/)

**Index**: `docs/setup/README.md` - Lists all setup guides with purpose and prerequisite info

---

### 2. troubleshooting/

**Purpose**: Help users diagnose and resolve problems
**Audience**: Users, operators, support staff
**Divio Type**: How-to (task-oriented, problem-solving)

**Scope**:
- Error diagnosis by symptom
- Service-specific issues
- Connectivity and performance problems
- Common failure scenarios
- Diagnostic procedures

**Organization**:
- Group by service (grafana, prometheus, backend, frontend)
- Group by symptom (connectivity, data, performance)
- Include quick diagnostics guide at top level

**Out of Scope**:
- Setup procedures (→ setup/)
- Development/debugging (→ development/)
- Known limitations (→ features/ or architecture/)

**Index**: `docs/troubleshooting/README.md` - Symptom-based navigation to guides

---

### 3. api/

**Purpose**: Technical reference for REST API endpoints, models, and contracts
**Audience**: API consumers, integrators, developers
**Divio Type**: Reference (information-oriented)

**Scope**:
- Endpoint specifications (paths, methods, parameters)
- Request/response models and schemas
- Authentication and authorization
- Error codes and responses
- API usage examples (code snippets)

**Organization**:
- `endpoints/` - By functional area (missions, pois, routes, etc.)
- `models/` - Data structures and schemas
- `examples/` - Language-specific usage examples
- `README.md` - API overview and quick reference

**Out of Scope**:
- Feature descriptions (→ features/)
- Implementation details (→ architecture/)
- Setup/configuration (→ setup/)

**Index**: `docs/api/README.md` - Endpoint categories, model reference, example guides

---

### 4. features/

**Purpose**: Describe system capabilities and user-facing functionality
**Audience**: Users, evaluators, product stakeholders
**Divio Type**: Explanation (understanding-oriented)

**Scope**:
- User-facing capabilities and workflows
- Feature descriptions and use cases
- System behavior and limitations
- Integration scenarios

**Organization**:
- One file per major feature area
- Organized by capability domain (monitoring, navigation, mission-planning, system)

**Out of Scope**:
- API specifications (→ api/)
- How-to guides (→ setup/ or troubleshooting/)
- Implementation (→ architecture/)

**Index**: `docs/features/README.md` - Feature catalog with brief descriptions

---

### 5. architecture/

**Purpose**: Explain system design, technical decisions, and internal structure
**Audience**: Developers, contributors, technical evaluators
**Divio Type**: Explanation (understanding-oriented, technical depth)

**Scope**:
- System architecture and component design
- Design decisions and rationale
- Data structures and models (internal)
- Technology choices and trade-offs
- Module organization and dependencies

**Organization**:
- `design-document.md` - High-level system architecture
- `data-structures/` - Internal data models and schemas
- Subsections for major subsystems if needed

**Out of Scope**:
- User-facing feature descriptions (→ features/)
- API specifications (→ api/)
- Development procedures (→ development/)

**Index**: `docs/architecture/README.md` - Architecture overview with links to deep dives

---

### 6. development/

**Purpose**: Guide developers on contributing, testing, and building the system
**Audience**: Contributors, developers
**Divio Type**: How-to (task-oriented, development workflows)

**Scope**:
- Development workflow and git practices
- Testing procedures and standards
- Code quality and contribution guidelines
- Tool-specific workflows (Claude Code, CI/CD)
- Development environment setup

**Organization**:
- Top-level: Common workflows (testing, contributing, development-workflow)
- `claude-code/` - AI-assisted development guides
- `testing/` - Test writing and execution guides (if many files)

**Out of Scope**:
- User-facing setup (→ setup/)
- Architecture explanations (→ architecture/)
- Contribution policy (root-level CONTRIBUTING.md)

**Index**: `docs/development/README.md` - Developer journey from onboarding to contribution

---

### 7. reports/

**Purpose**: Archive historical documentation and completed work artifacts
**Audience**: Project historians, retrospective reviewers
**Divio Type**: Archive (historical record)

**Scope**:
- Implementation completion summaries
- Feature analysis reports
- Retrospectives and post-mortems
- Migration and reorganization reports
- Phase completion documentation

**Organization**:
- `implementation-reports/` - Feature completion summaries
- `analysis-reports/` - Code/feature analysis artifacts
- `temp/` - Temporary work-in-progress (to be cleaned up)

**Requirements**:
- All files MUST include creation date in filename or frontmatter
- Files are frozen (not updated after completion)
- Clearly marked as historical context

**Out of Scope**:
- Current documentation (all other categories)
- Ongoing/active feature specs (→ specs/)

**Index**: `docs/reports/README.md` - Chronological listing of historical artifacts

---

## File Classification Rules

### Rule 1: Primary Audience Test

**Question**: Who is the primary reader?
- **User/Operator** → setup/, troubleshooting/, features/
- **Developer/Contributor** → development/, architecture/
- **API Consumer** → api/
- **Historian** → reports/

**Mixed audience** (no clear primary):
- Split into separate files, OR
- Use clear section headers and categorize by >60% content rule

---

### Rule 2: Content Type Test

**Question**: What is the documentation's primary purpose?
- **Getting started** → setup/
- **Problem-solving** → troubleshooting/
- **Technical reference** → api/ or architecture/
- **Capability description** → features/
- **Development process** → development/
- **Historical record** → reports/

---

### Rule 3: Scope Test (Backend-Specific vs. Project-Wide)

**Question**: Is this specific to one service implementation?
- **Service-specific** → Keep in backend/[service]/docs/
- **Project-wide** → Move to docs/

**Test**: "Would a frontend developer or another service need this?"
- YES → Project-wide (docs/)
- NO → Backend-specific (backend/*/docs/)

---

### Rule 4: Currency Test (Current vs. Historical)

**Question**: Is this documentation actively maintained?
- **Current** (updated with code) → Active categories
- **Historical** (frozen at completion) → reports/

**Indicators of historical**:
- Contains completion dates or "COMPLETE" status
- Describes past implementation phases
- Contains "summary" or "retrospective" in title

---

## Naming Conventions

### File Names

**Format**: `lowercase-with-hyphens.md`

**Examples**:
- `quick-start.md` (not `QUICK-START.md` or `QuickStart.md`)
- `installation.md` (not `install.md` or `INSTALLATION.md`)
- `mission-planning.md` (not `missionPlanning.md`)

**Exceptions**:
- Root-level: `README.md`, `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md` (uppercase by convention)
- Category indexes: `README.md` (always uppercase)

### Category Indexes

**Requirement**: Every category MUST have `README.md`

**Format**:
```markdown
# [Category Name]

**Purpose**: [One-sentence category purpose]
**Audience**: [Primary reader types]

## Documentation in This Category

### [Subcategory or Topic]

- **[Document Title]**: [One-sentence description]
- **[Document Title]**: [One-sentence description]

### [Another Topic]

- **[Document Title]**: [One-sentence description]

## Related Documentation

- [Links to related categories]
```

---

## Metadata Requirements

### Recommended Frontmatter

Not required, but recommended for complex documentation:

```markdown
---
title: [Document Title]
audience: [users|developers|operators|integrators]
category: [setup|api|features|etc.]
last_updated: YYYY-MM-DD
---
```

### Required Headers

Every documentation file MUST have:

1. **Top-level heading** (H1): Clear, descriptive title
2. **Purpose statement** (optional for small docs, required for >100 lines):
   - "This document describes..."
   - "For [audience], this guide covers..."

### Historical Documents

Files in `reports/` MUST include:
- **Date**: In filename (`2025-12-04-implementation-summary.md`) OR frontmatter
- **Status**: "COMPLETE" or "ARCHIVED" indicator
- **Context**: Brief description of why document was created

---

## Cross-Reference Strategy

### Link Format

**Always use relative paths**:
```markdown
<!-- Good -->
[Setup Guide](../setup/installation.md)
[API Reference](../../api/README.md)

<!-- Bad -->
[Setup Guide](/docs/setup/installation.md)  # Absolute path
[Setup Guide](docs/setup/installation.md)   # Root-relative path
```

### Anchor Links

**Use standard markdown anchors**:
```markdown
[Specific Section](../api/endpoints.md#authentication)
```

**Anchor format**: Lowercase, hyphens for spaces, special chars removed
- "Authentication Methods" → `#authentication-methods`
- "API v2.0 Endpoints" → `#api-v20-endpoints`

### Cross-Category Links

**Encouraged**: Link freely between categories to show relationships

**Best practices**:
- Link to category README.md for overview, specific docs for details
- Use descriptive link text: `[Mission Planning Features](../features/mission-planning.md)`, not `[click here](../features/mission-planning.md)`
- Avoid circular references (Category A index → B doc → A index)

---

## Organization Patterns

### Pattern 1: Flat Category (<15 files)

```
docs/features/
├── README.md
├── monitoring.md
├── navigation.md
├── mission-planning.md
└── system.md
```

**When to use**: Category has ≤15 documents

---

### Pattern 2: Subcategories (>15 files)

```
docs/api/
├── README.md         # Index to subcategories
├── endpoints/
│   ├── README.md     # Endpoint index
│   ├── missions.md
│   ├── pois.md
│   └── routes.md
├── models/
│   ├── README.md
│   ├── mission-models.md
│   └── poi-models.md
└── examples/
    ├── README.md
    ├── curl-examples.md
    └── python-examples.md
```

**When to use**: Category has >15 documents or natural subcategories exist

---

### Pattern 3: By Service/Symptom (troubleshooting/)

```
docs/troubleshooting/
├── README.md
├── quick-diagnostics.md  # Top-level, always visible
├── services/
│   ├── grafana.md
│   ├── prometheus.md
│   └── backend.md
└── connectivity/
    ├── live-mode.md
    └── performance.md
```

**When to use**: Need multiple navigation paths (by service OR by symptom)

---

## Size Guidelines

### Per Constitution (Principle IV)

- **Target**: ≤300 lines per file
- **Monitoring threshold**: Flag files >280 lines for split consideration
- **Split trigger**: Files >300 lines MUST be split unless justified

### Splitting Strategies

**Option 1: By subtopic**
- `api-reference.md` → `api-endpoints.md`, `api-models.md`, `api-examples.md`

**Option 2: By progression**
- `setup-guide.md` → `setup-prerequisites.md`, `setup-installation.md`, `setup-configuration.md`

**Option 3: By audience**
- `mission-planning.md` → `mission-planning-users.md`, `mission-planning-developers.md`

---

## Validation Checklist

Use this checklist to validate documentation organization:

- [ ] All categories have README.md index
- [ ] Top-level categories have <15 files (subcategories used if >15)
- [ ] All files use lowercase-with-hyphens naming
- [ ] All files ≤300 lines (justified if exceeds)
- [ ] All links use relative paths
- [ ] Historical docs have dates and "ARCHIVED" status
- [ ] Backend-specific docs remain in backend/*/docs/
- [ ] Only README.md, CLAUDE.md, AGENTS.md, CONTRIBUTING.md at root

---

## Summary

### Documentation Structure

```
docs/
├── setup/             (User: installation & configuration)
├── troubleshooting/   (User: problem-solving)
├── api/               (Developer: technical reference)
├── features/          (Both: capabilities)
├── architecture/      (Developer: design & decisions)
├── development/       (Developer: contributing & workflows)
└── reports/           (Archive: historical artifacts)
```

### Classification Flow

1. Identify primary audience (user vs. developer)
2. Identify content type (tutorial, how-to, reference, explanation, archive)
3. Apply scope test (project-wide vs. service-specific)
4. Apply currency test (current vs. historical)
5. Categorize using decision tree from research.md

### Key Principles

- **Separation of concerns**: User vs. developer documentation clearly separated
- **Discoverability**: Category indexes provide navigation
- **Maintainability**: <300 lines per file, clear organization
- **Portability**: Relative links, standard naming conventions

---

**Taxonomy Status**: ✓ Complete
**Ready for**: Contract definition and quickstart guide
