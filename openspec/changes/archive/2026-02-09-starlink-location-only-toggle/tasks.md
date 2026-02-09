## 1. Backend: StarlinkClient GPS Methods

- [x] 1.1 Add `get_gps_config()` method to `StarlinkClient` that extracts `gps_enabled`, `gps_ready`, and `gps_sats` from status data
- [x] 1.2 Add `set_gps_config(enable: bool)` method to `StarlinkClient` that calls `starlink_grpc.set_gps_config()` and returns updated state
- [x] 1.3 Add error handling for `PERMISSION_DENIED` gRPC errors in `set_gps_config()`

## 2. Backend: GPS Config API Endpoint

- [x] 2.1 Create Pydantic models for GPS config request/response (`GPSConfigRequest`, `GPSConfigResponse`)
- [x] 2.2 Create new router module `app/api/gps.py` with GPS config endpoints
- [x] 2.3 Implement GET `/api/v2/gps/config` endpoint that returns current GPS state
- [x] 2.4 Implement POST `/api/v2/gps/config` endpoint that updates GPS enabled state
- [x] 2.5 Add HTTP 503 error handling for dish unavailable scenarios
- [x] 2.6 Add HTTP 403 error handling for permission denied scenarios
- [x] 2.7 Register GPS router in main application

## 3. Frontend: GPS API Service

- [x] 3.1 Add TypeScript types for GPS config API (`GPSConfig`, `GPSConfigUpdate`)
- [x] 3.2 Create `gpsService.ts` with `getGPSConfig()` and `setGPSConfig()` functions
- [x] 3.3 Add error type handling for 403 and 503 responses

## 4. Frontend: GPS Control Card Component

- [x] 4.1 Create `GPSControlCard.tsx` component with card layout
- [x] 4.2 Add toggle switch for GPS enabled/disabled state
- [x] 4.3 Display GPS readiness indicator (ready/not ready)
- [x] 4.4 Display satellite count
- [x] 4.5 Add loading state during API requests (disable toggle, show spinner)
- [x] 4.6 Add error message display for permission denied and connectivity errors
- [x] 4.7 Fetch GPS status on component mount

## 5. Frontend: Integration

- [x] 5.1 Add `GPSControlCard` to appropriate dashboard or settings page
- [x] 5.2 Verify card styling matches existing UI patterns

## 6. Testing

- [x] 6.1 Add unit tests for `StarlinkClient.get_gps_config()` and `set_gps_config()` methods
- [x] 6.2 Add API endpoint tests for GET and POST `/api/v2/gps/config`
- [x] 6.3 Test error scenarios (dish unavailable, permission denied)
