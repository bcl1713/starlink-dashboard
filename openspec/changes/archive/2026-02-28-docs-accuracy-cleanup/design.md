## Context

Project documentation across ~30+ markdown files has drifted from the actual codebase. An audit identified 6 critical inaccuracies (wrong metric names, nonexistent model references, incorrect file structures), 7 medium gaps (undocumented endpoints, boilerplate READMEs, broken links), and 3 minor staleness issues (outdated dates, test counts, version numbers). This is a documentation-only change with zero runtime risk.

Two OpenSpec living specs also need updates: `mission-export` (references removed PDF/XLSX formats) and `export-performance` (references unimplemented cache logging).

## Goals / Non-Goals

**Goals:**
- Fix all 6 critical inaccuracies so docs match code exactly
- Repair broken and case-sensitive links across READMEs
- Document undocumented API endpoints (flight-status, GPS v2, starlink-csv, POI stats, GeoJSON variants, position-table)
- Bring OpenSpec living specs (`mission-export`, `export-performance`) into alignment with current implementation
- Update stale dates, version numbers, and feature lists

**Non-Goals:**
- No code changes of any kind
- No restructuring of the documentation hierarchy or tooling
- No new documentation standards or linting enforcement
- No changes to API behavior — only documenting what already exists
- No backfilling full API reference docs for every endpoint (just the undocumented ones identified in audit)

## Decisions

### Decision 1: Three-wave execution order

Fix inaccuracies first (Wave 1), then fill gaps (Wave 2), then freshen stale content (Wave 3). This prioritizes correctness over completeness — wrong information is more harmful than missing information.

**Alternative**: Single pass through all files alphabetically. Rejected because it mixes severity levels and makes it harder to checkpoint progress.

### Decision 2: Verify each fix against code before writing

Every documentation correction SHALL be verified against the actual source code, not just the audit notes. This prevents propagating stale audit findings.

**Alternative**: Trust the audit findings as-is. Rejected because the codebase may have changed since the audit was performed.

### Decision 3: Use delta specs for OpenSpec living spec updates

The `mission-export` and `export-performance` spec changes will use MODIFIED requirements in delta spec files, following the standard OpenSpec archive workflow. This keeps changes traceable and reviewable.

**Alternative**: Edit living specs directly. Rejected because it bypasses the change tracking workflow.

### Decision 4: Remove rather than stub missing link targets

For broken links pointing to files that don't exist (e.g., `./CONTRIBUTING.md`, `./dev/STATUS.md`), remove the links entirely rather than creating stub files. These files were never created and creating stubs would add maintenance burden.

**Alternative**: Create placeholder files. Rejected because it creates new maintenance obligations for content that was never authored.

## Risks / Trade-offs

- **[Concurrent code changes]** → Documentation fixes are based on current code state; if code changes land in parallel, some fixes may become stale again. Mitigation: Keep the change small and merge promptly.
- **[Audit completeness]** → The audit may have missed some inaccuracies. Mitigation: This change fixes known issues; future audits can catch remaining drift.
- **[MEMORY.md scope]** → Adding frontend deps to MEMORY.md may conflict with user preferences about what belongs there. Mitigation: Only add deps that are actively used and referenced in code.
