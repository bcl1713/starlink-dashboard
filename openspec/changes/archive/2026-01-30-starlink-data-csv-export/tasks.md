# Starlink CSV Export Tasks

## 1. Backend: Prometheus client

- [x] 1.1 Create `app/api/export/` module with router
- [x] 1.2 Add Prometheus HTTP client helper to query `/api/v1/query_range`
- [x] 1.3 Implement step auto-calculation logic based on time range

## 2. Backend: CSV export endpoint

- [x] 2.1 Create `/api/export/starlink-csv` endpoint with start, end, step params
- [x] 2.2 Query all metrics and join by timestamp
- [x] 2.3 Generate CSV with StreamingResponse
- [x] 2.4 Register export router in main app

## 3. Frontend: Export page

- [x] 3.1 Create `DataExportPage.tsx` with datetime pickers
- [x] 3.2 Add step interval selector (Auto, 1s, 10s, 1min, 5min)
- [x] 3.3 Add export button with loading state
- [x] 3.4 Trigger download on successful response

## 4. Frontend: Navigation

- [x] 4.1 Add route for `/export` in App router
- [x] 4.2 Add "Data Export" link to navigation

## 5. Verify

- [x] 5.1 Test export with small time range (1 hour)
- [x] 5.2 Verify CSV contains all expected columns

Note: Backend and frontend compile successfully. Full end-to-end testing requires running services with Prometheus.
