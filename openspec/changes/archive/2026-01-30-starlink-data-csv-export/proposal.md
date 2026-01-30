# Starlink Data CSV Export

## Why

Starlink telemetry data is collected and stored in Prometheus for monitoring, but there's no way to extract historical data for offline analysis, reporting, or archival. Users need to export raw data to CSV for data science workflows, compliance records, or sharing with teams that don't have Prometheus access.

## What Changes

- Add a backend API endpoint to query Prometheus and export historical telemetry as CSV
- Add a frontend UI to select date/time range and trigger the export
- Support all available metrics: position, network performance, obstruction, signal quality

## Capabilities

### New Capabilities

- `starlink-csv-export`: Export historical Starlink telemetry data to CSV file with configurable date/time range

## Impact

- `backend/starlink-location/app/api/` - New export endpoint
- `frontend/mission-planner/src/` - New export UI component/page
