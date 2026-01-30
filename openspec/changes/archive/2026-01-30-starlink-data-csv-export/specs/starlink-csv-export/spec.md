# Starlink CSV Export Spec

## ADDED Requirements

### Requirement: Date Range Selection

Users must be able to specify a start and end datetime for the export.

#### Scenario: Valid date range provided

- **WHEN** user specifies a start datetime and end datetime
- **AND** start is before end
- **AND** range is within the 1-year retention period
- **THEN** system queries Prometheus for data within that range
- **AND** returns CSV file with matching records

#### Scenario: Invalid date range

- **WHEN** user specifies start datetime after end datetime
- **THEN** system returns validation error
- **AND** no export is generated

### Requirement: Comprehensive Metric Export

The CSV must include all available Starlink telemetry metrics.

#### Scenario: Export includes all metric types

- **WHEN** user requests a CSV export
- **THEN** CSV includes columns for:
  - `timestamp` (ISO 8601)
  - `latitude`, `longitude`, `altitude_feet`, `speed_knots`, `heading_degrees`
  - `latency_ms`, `throughput_down_mbps`, `throughput_up_mbps`, `packet_loss_percent`
  - `obstruction_percent`
  - `signal_quality_percent`
- **AND** each row represents a single point in time

### Requirement: CSV Download

Users can download the export as a file.

#### Scenario: Successful download

- **WHEN** export completes successfully
- **THEN** browser downloads a file named `starlink-export-{start}-{end}.csv`
- **AND** file contains header row followed by data rows

### Requirement: Export UI

Frontend provides interface for configuring and triggering exports.

#### Scenario: User initiates export from UI

- **WHEN** user navigates to export page/dialog
- **THEN** user sees datetime pickers for start and end
- **AND** user sees export button
- **WHEN** user clicks export
- **THEN** system shows loading indicator
- **AND** download begins when complete
