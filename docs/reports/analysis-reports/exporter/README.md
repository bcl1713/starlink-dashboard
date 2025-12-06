# Mission Data Exporter Documentation

This directory contains documentation for the Mission Data Exporter feature,
which enables comprehensive export of mission data in multiple formats.

---

## Documentation

Due to their size, the original exporter documentation files have been preserved
and are available in this directory:

- **[ARCHITECTURE-ANALYSIS.md](./ARCHITECTURE-ANALYSIS.md)** (618 lines) -
  Detailed architecture analysis
- **[REFACTORING-PLAN.md](./REFACTORING-PLAN.md)** (567 lines) - Refactoring
  strategy and implementation
- **[SUMMARY.md](./SUMMARY.md)** (455 lines) - Feature summary and overview

---

## Quick Overview

The Mission Data Exporter provides:

- **Multiple Format Support:** PDF, PowerPoint, Excel, CSV
- **Comprehensive Data:** Routes, POIs, timeline, satellite coverage
- **Automated Generation:** Charts, maps, and tables
- **Production Ready:** 451 tests passing, full type coverage

### Export Formats

| Format         | Use Case                   | Features                            |
| -------------- | -------------------------- | ----------------------------------- |
| **PDF**        | Mission reports, briefings | Maps, charts, tables, professional  |
| \*\*PowerPoint | Presentations              | Slides, embedded images, animations |
| **Excel**      | Data analysis              | Multiple sheets, formulas, charts   |
| **CSV**        | Raw data export            | Simple, universal format            |

### Usage

```bash
# Export active mission to PDF
curl -X POST http://localhost:8000/api/missions/active/export/pdf \
  -o mission-report.pdf

# Export to PowerPoint
curl -X POST http://localhost:8000/api/missions/active/export/pptx \
  -o mission-briefing.pptx

# Export to Excel
curl -X POST http://localhost:8000/api/missions/active/export/xlsx \
  -o mission-data.xlsx
```

---

## Architecture

The exporter is organized into focused modules:

```text
app/api/missions/export/
├── __main__.py           # Export orchestration
├── map_generator.py      # Generate mission maps
├── chart_generator.py    # Generate charts and graphs
├── csv_exporter.py       # CSV export
├── xlsx_exporter.py      # Excel export
├── pdf_exporter.py       # PDF export
├── pptx_exporter.py      # PowerPoint export
└── data_transform.py     # Data transformation utilities
```

---

## Performance

- **Export time:** <5 seconds for typical mission
- **File sizes:** PDF (~2-5 MB), PPTX (~3-8 MB), XLSX (~500 KB)
- **Memory usage:** <256 MB per export
- **Concurrent exports:** Supported via async processing

--- [Back to Documentation Internal Index](../../../INDEX.md)
