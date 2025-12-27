# mission-export Specification Delta

## MODIFIED Requirements

### Requirement: Supported Export Formats

Mission and leg timeline exports MUST support CSV and PPTX formats only. PDF and XLSX formats are no longer supported to reduce complexity and improve performance.

**CHANGE:** Removed support for PDF and XLSX export formats. Only CSV (data analysis) and PPTX (presentations) are now supported.

#### Scenario: Export mission timeline as CSV

**Given** a mission with timeline data
**When** user requests CSV export
**Then** the system generates a CSV file with timeline segments, advisories, and statistics
**And** the CSV contains all data in machine-readable format suitable for analysis

#### Scenario: Export mission timeline as PPTX

**Given** a mission with timeline data
**When** user requests PPTX export
**Then** the system generates a PowerPoint presentation with:
- Title slide with mission metadata
- Route map slide with color-coded timeline status
- Timeline table slide with segment details
- Professional styling (gold headers/footers, logos, color-coded status)
**And** the PPTX is suitable for executive briefings and operational planning

#### Scenario: Request unsupported PDF format

**Given** a mission with timeline data
**When** user requests PDF export via API
**Then** the system returns a 400 Bad Request error
**And** the error message indicates "Unsupported export format: pdf"
**And** the error message suggests using PPTX for presentations or CSV for data

#### Scenario: Request unsupported XLSX format

**Given** a mission with timeline data
**When** user requests XLSX export via API
**Then** the system returns a 400 Bad Request error
**And** the error message indicates "Unsupported export format: xlsx"
**And** the error message suggests using CSV for tabular data

#### Scenario: Mission package contains only CSV and PPTX

**Given** a mission with 2 legs
**When** user exports the mission as a package (ZIP file)
**Then** the package contains:
- Per-leg exports: `exports/legs/{leg-id}/timeline.csv` for each leg
- Per-leg exports: `exports/legs/{leg-id}/slides.pptx` for each leg
- Mission-level exports: `exports/mission/mission-timeline.csv`
- Mission-level exports: `exports/mission/mission-slides.pptx`
**And** the package does NOT contain any `.pdf` or `.xlsx` files
**And** the total file count is 6 (4 leg files + 2 mission files)

#### Scenario: Export performance improvement

**Given** a mission with 2 legs requiring timeline exports
**When** the mission package is generated
**Then** the export completes in approximately 50% less time compared to generating 4 formats
**And** no PDF or XLSX generation overhead occurs

### Requirement: Migration Path for Legacy Formats

Users requiring PDF or XLSX functionality MUST use alternative approaches since these formats are no longer supported.

**CHANGE:** Added migration guidance for users who previously relied on PDF/XLSX exports.

#### Scenario: User needs PDF output

**Given** a user previously relied on PDF exports
**When** they need a PDF version of mission data
**Then** they should export as PPTX
**And** convert PPTX to PDF using PowerPoint, LibreOffice, or online converters
**And** the PDF retains all visual styling and content from PPTX

#### Scenario: User needs XLSX output

**Given** a user previously relied on XLSX exports
**When** they need Excel-compatible data
**Then** they should export as CSV
**And** import CSV into Excel, LibreOffice Calc, or Google Sheets
**And** the tabular data is fully preserved

#### Scenario: Automated systems request PDF/XLSX

**Given** an automated system configured to download PDF or XLSX exports
**When** the system makes an API request with format=pdf or format=xlsx
**Then** the API returns a 400 error with clear message
**And** the error message includes recommended format alternatives
**And** system administrators can update automation to use CSV or PPTX

## REMOVED Requirements

The following requirements are removed because PDF and XLSX exports are no longer supported:

### ~~Requirement: Professional PDF Styling~~

**REMOVED:** PDF export functionality has been eliminated. Users needing PDF should export PPTX and convert externally.

### ~~Requirement: XLSX Export with Embedded Images~~

**REMOVED:** XLSX export functionality has been eliminated. Users needing tabular data should use CSV format.

### ~~Requirement: Multi-Sheet XLSX Workbook~~

**REMOVED:** Combined mission-level XLSX workbooks are no longer generated. Use CSV for data analysis.
