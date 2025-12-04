# Export Module Refactoring Plan

## Quick Reference

### Files to Refactor

- **exporter.py** (2220 lines) - Single-leg timeline export with 4 formats (CSV,
  XLSX, PDF, PPTX)
- **package_exporter.py** (1298 lines) - Mission-level packaging and archive
  creation
- **Total:** 3518 lines, highly interdependent

### Current Architecture Issues

1. **Mixed Concerns:** Formatting, data processing, rendering, and packaging all
   in two files
1. **Visualization Bloat:** Map/chart generation adds ~700 lines to exporter.py
1. **Code Reuse Problems:** Combined export functions duplicate
   pagination/styling logic from single-leg exports
1. **Tight Coupling:** Manager dependencies deeply nested in visualization code

---

## Plan Sections

### 1. [Refactoring Roadmap](plan/ROADMAP.md)

Detailed roadmap covering Phases 1 through 6 of the refactoring effort,
including specific modules to extract and their benefits.

### 2. [Implementation Strategy](plan/IMPLEMENTATION.md)

Execution details including the refactoring sequence (timeline), testing
strategy, file size estimates, dependency graph, backward compatibility, and
risk assessment.
