# Mission Data Exporter Documentation

This directory contains documentation for the Mission Data Exporter feature,
which enables comprehensive export of mission data in multiple formats.

---

## Documentation

Due to their size, the original exporter documentation files have been preserved
and are available in this directory:

- **[architecture-analysis.md](./architecture-analysis.md)** (618 lines) -
  Detailed architecture analysis
- **[refactoring-plan.md](./refactoring-plan.md)** (567 lines) - Refactoring
  strategy and implementation
- **[summary.md](./summary.md)** (455 lines) - Feature summary and overview

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

The retired mission API does not provide supported export commands. Mission V2
introduces no replacement exporter endpoint in this documentation; retain
approved reports through the operational archive process rather than calling a
retired route.

---

## Retired exporter architecture

The listed exporter implementation belongs to the retired mission API and is
not an operator interface. Mission V2 does not define a replacement exporter
endpoint in this documentation.

---

## Performance

- **Export time:** <5 seconds for typical mission
- **File sizes:** PDF (~2-5 MB), PPTX (~3-8 MB), XLSX (~500 KB)
- **Memory usage:** <256 MB per export
- **Concurrent exports:** Supported via async processing

--- [Back to Documentation Internal Index](../../../index.md)
