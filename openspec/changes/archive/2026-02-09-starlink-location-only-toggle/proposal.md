## Why

The Starlink dish has a built-in GPS receiver that can provide location data, but users currently have no way to control whether the dish uses this GPS for position determination. The gRPC API exposes a `dish_inhibit_gps` call and a `set_gps_config()` wrapper function that are available but not yet integrated into the application. Users may want to disable GPS usage (forcing the dish to use cached/internal location) for various reasons such as privacy, testing, or when GPS reception is poor.

## What Changes

- Add a new backend API endpoint to get and set the GPS enable/disable state via the existing `starlink_grpc.set_gps_config()` function
- Add a frontend toggle control to allow users to enable/disable GPS location usage on the Starlink dish
- Display current GPS status (enabled, ready, satellite count) alongside the toggle for user feedback

## Capabilities

### New Capabilities

- `gps-location-control`: Backend API and frontend UI for controlling whether the Starlink dish uses GPS for position data. Includes GET/SET endpoints and a toggle with status display.

### Modified Capabilities

(none - this is additive functionality)

## Impact

- **Backend**: New API endpoint(s) in the starlink-location service under `/api/v2/` prefix
- **Frontend**: New UI component in the mission-planner app (likely in TimingSection or a dedicated settings area)
- **gRPC**: Uses existing `dish_inhibit_gps` gRPC call via `starlink_grpc.set_gps_config()` wrapper
- **Permissions**: May require appropriate permissions on the Starlink dish to modify GPS settings
- **State**: GPS enable/disable state is persisted on the dish itself (not application-level storage)
