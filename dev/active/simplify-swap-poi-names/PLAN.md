# Plan: Simplify Swap POI Names

**Branch:** `feat/simplify-swap-poi-names`
**Slug:** `simplify-swap-poi-names`
**Folder:** `dev/active/simplify-swap-poi-names/`
**Date:** 2025-11-22
**Owner:** brian
**Status:** Completed

---

## Executive Summary

This work simplifies the naming of X-Band and CommKa satellite swap Point of Interest (POI) markers in the Starlink mission monitoring system. Currently, swap POIs display detailed satellite names (e.g., "X-Band\nX-1→X-2" or "CommKa\nAOR→POR"), which provide non-actionable information for operators. The change will replace these with simple labels: "X-Band\nSwap" and "CommKa\nSwap" for transition events, and "CommKa\nExit" and "CommKa\nEntry" for gap events (without satellite names). This affects POI generation in the backend timeline service, which flows through to database entries, Grafana map displays, and all exported mission documents (CSV, XLSX, PDF, PPTX). The change is forward-only; existing POIs retain their current names.

---

## Objectives

The work will be complete when the following **testable outcomes** are achieved:

- X-Band swap POIs display as "X-Band\nSwap" (no satellite names) in newly generated missions
- CommKa transition swap POIs display as "CommKa\nSwap" (no satellite names) in newly generated missions
- CommKa gap exit POIs display as "CommKa\nExit" (no satellite names) in newly generated missions
- CommKa gap entry POIs display as "CommKa\nEntry" (no satellite names) in newly generated missions
- AAR POI naming remains unchanged ("AAR\nStart" / "AAR\nEnd")
- Simplified names appear correctly in Grafana map displays
- Simplified names appear correctly in exported mission documents (CSV, XLSX, PDF, PPTX)
- All existing tests pass with the new naming convention

---

## Phases

### **Phase 1 — Preparation**

**Description:**
Review the current POI naming implementation, confirm the exact code locations, and validate the testing approach.

**Entry Criteria:**

- Scope locked
- Branch created
- Plan documents initialized

**Exit Criteria:**

- Code locations confirmed in timeline_service.py
- Testing strategy documented
- CHECKLIST.md populated with implementation tasks

---

### **Phase 2 — Implementation**

**Description:**
Modify the three POI naming functions in timeline_service.py to return simplified labels without satellite names.

**Entry Criteria:**

- Checklist initialized
- Backend service accessible for testing

**Exit Criteria:**

- `_format_commka_exit_entry()` updated to remove satellite names
- `_format_commka_transition_label()` updated to return "CommKa\nSwap"
- `_format_x_transition_label()` updated to return "X-Band\nSwap"
- Code changes committed

---

### **Phase 3 — Verification**

**Description:**
Rebuild Docker containers, test POI generation with a sample mission, and verify the simplified names appear correctly in all outputs.

**Entry Criteria:**

- Implementation complete
- Docker environment functional

**Exit Criteria:**

- Docker containers rebuilt with `--no-cache`
- New mission POIs show simplified names via `/api/pois` endpoint
- Grafana map displays simplified POI labels
- Exported documents (CSV, XLSX, PDF, PPTX) contain simplified names
- All existing unit/integration tests pass

---

### **Phase 4 — Documentation & Wrap-Up**

**Description:**
Update plan documents, capture any lessons learned, and prepare for PR creation.

**Entry Criteria:**

- Verification complete
- All acceptance criteria met

**Exit Criteria:**

- PLAN.md status updated to "Completed"
- CONTEXT.md finalized with any discovered constraints
- CHECKLIST.md fully completed
- LESSONS-LEARNED.md updated if applicable
- Ready for PR creation via wrapping-up-plan skill
