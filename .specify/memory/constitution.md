<!--
  SYNC IMPACT REPORT (v1.0.1)
  ===========================
  Version Change: 1.0.0 → 1.0.1 (PATCH: Linting discipline clarification)
  Modified Sections: Code Formatting & Linting (added markdownlint-cli2, disabled comment policy)
  Templates Updated:
    - plan-template.md: ✅ Compatible with Constitution Check gate
    - spec-template.md: ✅ Compatible with user story prioritization
    - tasks-template.md: ✅ Compatible with task formatting
  Follow-up TODOs: None
-->

# Starlink Dashboard Constitution

A living document governing code quality, documentation standards, and interface design for the Starlink Dashboard project.

## Core Principles

### I. Clean, Human-Readable Code

Every code file MUST prioritize clarity and maintainability as non-negotiable requirements.

**Rules:**
- Code MUST be self-documenting through clear variable/function names and logical structure
- Comments MUST explain the "why," not the "what" (code is self-evident, intent is not)
- Functions MUST be single-responsibility and under 50 lines (strong preference)
- Type hints and docstrings MUST be present in Python (PEP 257 style) and TypeScript/JavaScript (JSDoc)
- No clever, dense, or overly compact code—readability always wins over cleverness
- Files MUST maintain consistent indentation (2 spaces for YAML/JSON, 4 for Python, per `.editorconfig`)

**Rationale:** Code is read far more often than written. Clear code reduces cognitive load, speeds onboarding, minimizes bugs, and makes maintenance sustainable.

### II. Current & Complete Documentation

Documentation MUST be accurate, up-to-date, and address both developer and user needs equally.

**Rules:**
- README.md and all user-facing docs MUST reflect current system state (tested on each merge)
- API documentation MUST be generated from code (e.g., FastAPI `/docs`, JSDoc) and kept in sync
- Architecture decisions MUST be documented in `docs/design-document.md` with date and rationale
- Setup guides MUST include troubleshooting section with common failures and solutions
- Code comments and docstrings MUST not be stale—update them when behavior changes
- For users: provide step-by-step examples and expected output; for developers: provide architectural context and code organization

**Rationale:** Outdated documentation causes confusion, wasted debugging time, and lost trust. Current docs are a competitive advantage and reduce support burden.

### III. Responsive, Appropriately-Themed Interfaces

All user interfaces MUST be responsive, performant, and visually consistent with the Starlink Dashboard brand.

**Rules:**
- Frontend MUST be responsive to viewport widths from 375px (mobile) to 4K+ (desktop)
- Grafana dashboards MUST follow the established color scheme and icon conventions
- UI MUST load and interact within 2 seconds on typical network (p95 latency target)
- Darkmode MUST be supported (default) or explicitly documented as unsupported
- Accessibility MUST meet WCAG 2.1 AA standards (color contrast, keyboard navigation, screen reader support)
- All external APIs MUST have a test/stub mode (e.g., simulation mode for Starlink)

**Rationale:** Users interact with interfaces more frequently than code. Poor UX creates frustration and reduces adoption. Responsive design ensures usability across devices; theming consistency builds brand trust.

### IV. File Size Limits for Maintainability

Source code and documentation files MUST not exceed 300 lines (with allowed exceptions).

**Rules:**
- Python files MUST not exceed 300 lines; split into multiple modules or packages beyond this
- TypeScript/JavaScript files MUST not exceed 300 lines; use component decomposition or split services
- Markdown files MUST not exceed 300 lines; link to additional files or create a series instead
- **Exceptions** (allowed only when justified):
  - Database migrations (auto-generated) – no limit
  - Generated code (e.g., OpenAPI specs, protobuf) – no limit
  - Lock files (`package-lock.json`, `requirements.txt`) – no limit
  - Test fixtures (large JSON/data) – no limit
  - Configuration files (>300 but <500 lines only if refactoring is infeasible)
- Files exceeding 300 lines MUST include a comment explaining why refactoring was deferred

**Rationale:** Large files are harder to understand, test, and maintain. The 300-line limit forces natural decomposition and keeps cognitive load manageable. Exceptions exist for generated/auto-managed content that developers don't edit.

## Development & Quality Standards

### Code Formatting & Linting

- **Python:** Format with Black (line length 88), lint with rg-based checks, type-check with mypy
- **TypeScript/JavaScript:** Format with Prettier (print width 80, prose wrap always), lint with ESLint
- **YAML/JSON:** Format with Prettier, validate schema where applicable
- **Markdown:** Format with Prettier (prose wrap always, single/double quotes per context), lint with markdownlint-cli2
- **Linting Discipline:** No inline comments to disable ESLint or Markdown linting rules (e.g., no `// eslint-disable`, no `<!-- markdownlint-disable -->`)—violations indicate code quality issues that must be addressed, not suppressed
- All tools MUST run in pre-commit hooks; violations block commits (configurable for CI bypass)

### Testing Discipline

- Unit tests MUST cover critical paths and error conditions (aim for >70% coverage on core modules)
- Integration tests MUST verify inter-service communication (e.g., API contracts, Prometheus scraping)
- Contract tests MUST be present for all API endpoints before merging
- Tests MUST be run on every commit (enforced in CI); failures block merge
- No "skip" markers in version control (temporary @skip/@pytest.skip allowed locally only)

### Observability & Debugging

- All services MUST expose structured logs in JSON format (via Python logging / Node.js winston)
- Critical operations MUST log entry and exit with relevant context (user ID, request ID, etc.)
- Error logs MUST include stack traces and actionable context, not cryptic codes
- Metrics MUST be exposed via Prometheus (for backend) with human-readable names
- Health checks MUST be available at `/health` endpoint (or equivalent) and must include version and mode info

### Versioning & Breaking Changes

- Project version follows Semantic Versioning (MAJOR.MINOR.PATCH)
- MAJOR bumps indicate breaking changes (API incompatibility, database schema changes)
- MINOR bumps indicate new features (backward compatible)
- PATCH bumps indicate bug fixes and documentation updates
- All breaking changes MUST be documented in CHANGELOG.md with migration steps

## Governance

**Constitution Compliance:**
- All pull requests MUST pass a Constitution Check gate before review (verify code length, doc updates, test presence)
- Complex features that violate this constitution (e.g., files >300 lines) require explicit justification in PR description
- Justifications must be approved by project maintainer and tracked in a "Complexity Justifications" section of the feature plan

**Amendment Process:**
- Changes to this constitution require a merge request documenting the amendment rationale
- Amendments MUST update dependent templates (plan-template.md, spec-template.md, tasks-template.md)
- Amendments MUST update this file's version and Last Amended date
- Significant amendments require team discussion before merging

**Compliance Review:**
- Monthly: Review merged PRs against constitution principles (audit sample of 10% of commits)
- Quarterly: Review documentation freshness (README.md, API docs, architecture docs)
- On-demand: Before major releases, audit test coverage and observability metrics

**Use Guidance:**
- Runtime development guidance is documented in `CLAUDE.md` (global) and project `CLAUDE.md` (repo-specific)
- CLAUDE.md is the canonical source for tool workflows, CI/CD procedures, and environment-specific instructions
- This constitution defines the "what" and "why"; CLAUDE.md defines the "how"

---

**Version**: 1.0.1 | **Ratified**: 2025-12-02 | **Last Amended**: 2025-12-02
