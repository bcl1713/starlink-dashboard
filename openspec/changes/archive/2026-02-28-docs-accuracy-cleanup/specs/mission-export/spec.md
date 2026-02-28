## MODIFIED Requirements

### Requirement: Backward Compatibility

PPTX styling enhancements MUST NOT affect the CSV export format
or change the PowerPoint file structure. References to PDF and XLSX formats
are removed since those formats are no longer supported.

#### Scenario: CSV export format unchanged

**Given** a mission with timeline data
**When** user exports as CSV
**Then** the output format and content remain identical to pre-enhancement behavior
**And** no visual styling changes are applied to the CSV output

#### Scenario: PowerPoint file structure preserved

**Given** a mission export as PowerPoint
**When** the PPTX file is generated
**Then** the file remains a valid PPTX file readable by PowerPoint, LibreOffice,
and other presentation software
**And** the slide count matches pre-enhancement behavior
**And** existing automation/scripts that process PPTX exports continue to work
