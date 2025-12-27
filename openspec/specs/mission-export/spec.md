# mission-export Specification

## Purpose
TBD - created by archiving change enhance-pptx-styling. Update Purpose after archive.
## Requirements
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

### Requirement: Professional PPTX Styling

PowerPoint exports MUST use professional styling with branded colors, headers,
footers, and visual hierarchy suitable for executive briefings and operational
planning.

**CHANGE:** Footer text styling and positioning updated for better visual
integration with gold bar branding, and mission date now displays actual leg
start date instead of export generation time.

#### Scenario: Export leg with styled route map slide

**Given** a mission leg with a route and map
**When** user exports the mission as PowerPoint
**Then** each route map slide includes:

- Gold header bar and footer bar (0.15" height each)
- Light gray content background (RGB 248, 249, 250)
- Slide title "Leg X - Route Map" in 24pt bold
- Route map image centered within content area
- **Footer text with mission leg start date, mission ID, and organization**
- **Footer text positioned within the gold bar (y=5.47 inches)**
- **Footer text styled as 7pt white font for readability on gold background**
- Logo image in top-left corner (if exists)

#### Scenario: Export leg with color-coded timeline slide

**Given** a mission leg with timeline segments including NOMINAL, SOF,
DEGRADED, and CRITICAL statuses
**When** user exports the mission as PowerPoint
**Then** each timeline slide includes:

- Gold header bar and footer bar
- Light gray content background
- Slide title "Leg X - Timeline" in 24pt bold
- Each segment row displays:
  - Segment number (11pt bold)
  - Color-coded status badge with white text (11pt bold):
    - NOMINAL: Green (RGB 22, 163, 74)
    - SOF: Blue (RGB 2, 132, 199)
    - DEGRADED: Orange (RGB 234, 88, 12)
    - CRITICAL: Red (RGB 220, 38, 38)
  - Start time, end time, duration, reason
  - Transport state indicators (✓ or ⚠)
- Visual separator (1px gray line) between segments
- **Footer with "Date: YYYY-MM-DD | Mission ID | Organization" where date
  is the mission leg start date**
- **Footer text positioned within the gold bar (y=5.47 inches)**
- **Footer text styled as 7pt white font**
- Logo image (if exists)

#### Scenario: Mission leg date displays correctly

**Given** a mission leg with timeline segments starting at 2025-01-15 10:00:00
UTC
**And** the PowerPoint is exported on 2025-01-20 14:30:00 UTC
**When** user opens the generated PowerPoint file
**Then** the footer displays "Date: 2025-01-15 | ..." (the leg start date)
**And** the footer does NOT display 2025-01-20 (the export generation date)

#### Scenario: Mission with no timeline segments

**Given** a mission leg with no timeline segments
**When** user exports the mission as PowerPoint
**Then** the footer date falls back to the timeline creation timestamp
**And** the export succeeds without error

#### Scenario: Footer text is readable within gold bar

**Given** any mission leg exported to PowerPoint
**When** user views the slides in presentation mode
**Then** the footer text appears inside the gold bar at the bottom
**And** the white 7pt text is clearly readable against the gold background
(RGB 212, 175, 55)
**And** the text is centered horizontally within the slide

### Requirement: Backward Compatibility

PPTX styling enhancements MUST NOT affect other export formats (CSV, XLSX, PDF)
or change the PowerPoint file structure.

#### Scenario: Other export formats unchanged

**Given** a mission with timeline data
**When** user exports as CSV, XLSX, or PDF
**Then** the output format and content remain identical to pre-enhancement behavior
**And** no visual styling changes are applied to these formats

#### Scenario: PowerPoint file structure preserved

**Given** a mission export as PowerPoint
**When** the PPTX file is generated
**Then** the file remains a valid PPTX file readable by PowerPoint, LibreOffice,
and other presentation software
**And** the slide count matches pre-enhancement behavior
**And** existing automation/scripts that process PPTX exports continue to work

