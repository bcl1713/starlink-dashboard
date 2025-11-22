# Plan: Replace HCX and WGS terminology

**Branch:** `chore/term-replacements`
**Slug:** `term-replacements`
**Folder:** `dev/active/term-replacements/`
**Date:** 2025-11-22
**Owner:** Brian
**Status:** Planning

---

## Executive Summary

This work standardizes satellite communication band terminology throughout the codebase by replacing HCX with CommKa and WGS with X-Band. The changes affect ~180 occurrences across 37 files, primarily in documentation, test data, and display labels. This is a straightforward refactoring that improves terminology consistency while preserving all scientific constants and infrastructure names (Docker services, modules, Starlink references remain unchanged). Success means all user-facing labels, configuration references, and documentation reflect the new terminology without breaking any functionality.

---

## Objectives

The work will be complete when the following **testable outcomes** are achieved:

- All HCX references replaced with CommKa (~164 occurrences across 31 files)
- All WGS satellite name references replaced with X-Band (~15 occurrences across 6 files)
- WGS84 geodetic constants preserved unchanged
- File renames completed (HCX.kmz → CommKa.kmz, hcx.geojson → commka.geojson)
- All Python code syntax valid and imports functional
- Backend health check passes and services remain operational
- Grafana dashboards load and display new terminology correctly
- All tests pass with updated assertions

---

## Phases

### **Phase 1 — Preparation & Validation**

**Description:**
Identify all files requiring changes, validate file paths, and ensure all tools are ready. Confirm the current state of assets before any modifications.

**Entry Criteria:**

- Scope locked
- Branch created
- Research complete on file locations

**Exit Criteria:**

- Checklist created with specific file paths
- All target files verified to exist
- Backup verification of current filenames and content

---

### **Phase 2 — WGS Replacements (Low Risk)**

**Description:**
Replace WGS satellite name references with X-Band. This is low-risk as it affects only test data and documentation, not core functionality.

**Entry Criteria:**

- Preparation phase complete
- Checklist initialized

**Exit Criteria:**

- All WGS → X-Band replacements in 6 files complete
- WGS84 constants untouched
- Tests passing with updated test data
- Commit created for WGS changes

---

### **Phase 3 — HCX Replacements (Medium Risk)**

**Description:**
Replace HCX with CommKa across all 31 files. This includes file renames, display constants, function names, variable names, and documentation. Execute in careful order to maintain consistency.

**Entry Criteria:**

- Phase 2 complete

**Exit Criteria:**

- All HCX → CommKa replacements complete across 31 files
- File renames successful
- Variable/function names updated
- Documentation and tests updated
- Python syntax valid
- Commit created for HCX changes

---

### **Phase 4 — Verification & Testing**

**Description:**
Validate all changes work correctly, verify file structure intact, and confirm no functionality broken.

**Entry Criteria:**

- Phases 2-3 complete

**Exit Criteria:**

- Syntax validation passed
- Backend health check successful
- All tests execute without errors
- Grafana dashboard displays correctly
- Manual smoke tests confirm display labels updated

---

### **Phase 5 — Documentation & Wrap-Up**

**Description:**
Update plan documents, finalize changes, and prepare PR for merge.

**Entry Criteria:**

- Verification complete

**Exit Criteria:**

- PLAN.md updated to "Completed"
- CONTEXT.md finalized
- CHECKLIST.md fully completed
- PR created and ready for review
