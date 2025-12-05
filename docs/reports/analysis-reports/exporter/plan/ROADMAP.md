# Refactoring Roadmap

This document outlines the step-by-step plan for refactoring the export module.

## Roadmap Sections

### 1. [Phases 1-3: Foundation, Data & Rendering](roadmap/PHASES-1-3.md)

- **Phase 1:** Extracting pure utilities (formatting, excel, transport utils).
- **Phase 2:** Separating the data processing layer (data builders, segment
  processing).
- **Phase 3:** Abstracting map and chart rendering logic.

### 2. [Phases 4-6: Formats, Packaging & Multi-Leg](roadmap/PHASES-4-6.md)

- **Phase 4:** Creating dedicated modules for each export format (CSV, XLSX,
  PDF, PPTX).
- **Phase 5:** Separating package assembly and archive creation.
- **Phase 6:** Handling combined mission exports and multi-leg aggregation.
