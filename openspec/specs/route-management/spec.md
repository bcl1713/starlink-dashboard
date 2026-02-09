# route-management Specification Delta

## ADDED Requirements

### Requirement: Route Manager Page

The system SHALL provide a dedicated Route Manager page at `/routes` in the React frontend with a split layout showing a route list (left) and route detail view (right).

#### Scenario: Access Route Manager from navigation

**Given** the user is on any page in the React frontend
**When** the user clicks the "Routes" link in the main navigation bar
**Then** the browser navigates to `/routes`
**And** the Route Manager page loads
**And** the left pane displays a table of all routes
**And** the right pane is empty with text "Select a route to view details"

#### Scenario: View route list

**Given** 5 routes exist in the system
**And** 1 route is active
**When** the Route Manager page loads
**Then** the route list displays all 5 routes in a table
**And** each row shows: name, point count, timing profile summary, flight phase, active status
**And** the active route row is highlighted with a distinct background color
**And** each row has action buttons: View Details, Activate/Deactivate, Download, Delete

### Requirement: Route Upload via KML

The system SHALL provide a drag-and-drop KML file upload interface with optional POI import from waypoint placemarks.

#### Scenario: Upload KML file with drag-and-drop

**Given** the user is on the Route Manager page
**When** the user clicks the "Upload Route" button
**Then** a modal dialog opens with a drag-drop zone
**When** the user drags a file "route-alpha.kml" into the drop zone
**And** drops the file
**Then** a loading indicator is displayed
**And** a POST request is sent to `/api/routes/upload?import_pois=true` with multipart/form-data
**When** the upload completes successfully
**Then** the dialog shows a success message "Route uploaded: route-alpha"
**And** the route list automatically refreshes
**And** the new route appears in the list
**And** the dialog displays import statistics (e.g., "5 POIs imported, 2 skipped")

#### Scenario: Upload KML with POI import disabled

**Given** the user is uploading a KML file
**When** the user unchecks the "Import waypoints as POIs" checkbox
**And** uploads the file
**Then** the request is sent to `/api/routes/upload?import_pois=false`
**And** waypoint placemarks are not imported as POIs
**And** the success message shows "0 POIs imported"

#### Scenario: Upload invalid KML file

**Given** the user attempts to upload a malformed KML file
**When** the file is uploaded
**Then** the API returns a 400 Bad Request error
**And** an error message is displayed: "Failed to parse KML file"
**And** the route is not added to the list

#### Scenario: Upload non-KML file rejected

**Given** the user is on the upload dialog
**When** the user attempts to select a file with extension .gpx or .geojson
**Then** the file input rejects the file
**And** a validation message is displayed: "Only .kml files are allowed"

### Requirement: Route Activation and Deactivation

The system SHALL allow users to activate and deactivate routes with visual feedback and automatic POI projection calculation.

#### Scenario: Activate route

**Given** a route exists with id "route-alpha" in inactive state
**And** another route "route-beta" is currently active
**When** the user clicks the "Activate" button for "route-alpha"
**Then** a POST request is sent to `/api/routes/route-alpha/activate`
**And** a loading spinner is shown on the button
**When** the request succeeds
**Then** "route-alpha" is marked as active
**And** "route-beta" is automatically deactivated
**And** the route list refreshes
**And** "route-alpha" row is highlighted as active
**And** all POIs associated with "route-alpha" recalculate their projections
**And** a success message is displayed: "Route activated: route-alpha"

#### Scenario: Deactivate active route

**Given** a route "route-alpha" is currently active
**When** the user clicks the "Deactivate" button
**Then** a POST request is sent to deactivate the route
**When** the request succeeds
**Then** "route-alpha" is marked as inactive
**And** the route list refreshes with no highlighted row
**And** all POI projections are cleared
**And** a success message is displayed: "Route deactivated"

#### Scenario: Only one route can be active

**Given** route "route-alpha" is active
**When** the user activates route "route-beta"
**Then** the system automatically deactivates "route-alpha"
**And** only "route-beta" is active
**And** the route list shows only one highlighted row

### Requirement: Route Detail View

The system SHALL display detailed route information including map visualization, metadata, statistics, timing profile, and associated POIs when a route is selected.

#### Scenario: View route details with map

**Given** a route exists with 150 waypoints and 8 associated POIs
**When** the user clicks the route row in the list
**Then** the right pane displays the route detail view
**And** the route map is rendered using the RouteMap component
**And** the route line is drawn connecting all 150 waypoints
**And** the map shows the 8 associated POI markers
**And** the map auto-zooms to fit the entire route bounds

#### Scenario: View route metadata and statistics

**Given** a route "Flight Path Alpha" is selected
**And** the route has 200 points
**And** the route total distance is 1250.5 km
**When** the route detail view loads
**Then** the metadata section displays:
- Name: "Flight Path Alpha"
- Description: (route description if available)
- Point Count: 200
- Distance: 1250.5 km
- Imported At: (timestamp)
- Bounds: min/max latitude and longitude

#### Scenario: View route timing profile

**Given** a route has timing profile with:
- Departure time: 2025-01-15 10:00:00 UTC
- Arrival time: 2025-01-15 14:30:00 UTC
- Flight status: "pre_departure"
**When** the route detail view loads
**Then** the timing profile section displays:
- Departure: "2025-01-15 10:00 UTC"
- Arrival: "2025-01-15 14:30 UTC"
- Duration: "4h 30min"
- Flight Status: "pre_departure" badge (orange)
**And** the ETA mode is displayed as "anticipated"

#### Scenario: View associated POIs

**Given** a route is selected
**And** 5 POIs are associated with the route
**When** the route detail view loads
**Then** the "Associated POIs" section displays a table with the 5 POIs
**And** each POI row shows: name, coordinates, category, active status
**And** clicking a POI row opens the POI Manager page with that POI selected

### Requirement: Route Deletion

The system SHALL allow users to delete routes with confirmation and cascade deletion of associated POIs.

#### Scenario: Delete route with confirmation

**Given** a route "route-alpha" exists
**And** the route has 3 associated POIs
**When** the user clicks the "Delete" button for the route
**Then** a confirmation dialog appears with message:
"Are you sure you want to delete 'route-alpha'? This will also delete 3 associated POIs."
**When** the user clicks "Confirm"
**Then** a DELETE request is sent to `/api/routes/route-alpha`
**And** the route is removed from the list
**And** the 3 associated POIs are also deleted
**And** if the route detail view was open, it is cleared
**And** a success message is displayed: "Route deleted: route-alpha"

#### Scenario: Cancel route deletion

**Given** the user has clicked the "Delete" button for a route
**And** the confirmation dialog is displayed
**When** the user clicks "Cancel"
**Then** the dialog closes
**And** the route is not deleted
**And** the route remains in the list

#### Scenario: Prevent deletion of active route

**Given** a route is currently active
**When** the user attempts to delete the route
**Then** the confirmation dialog includes an additional warning:
"This route is currently active. Deleting it will deactivate it first."
**When** the user confirms
**Then** the route is deactivated
**And** then deleted

### Requirement: Route Download

The system SHALL allow users to download route KML files with proper filename and MIME type.

#### Scenario: Download route KML file

**Given** a route exists with name "route-alpha.kml"
**When** the user clicks the "Download" button
**Then** a GET request is sent to `/api/routes/{route_id}/download`
**And** the response is a Blob with MIME type "application/vnd.google-earth.kml+xml"
**And** the browser initiates a file download
**And** the downloaded file is named "route-alpha.kml"
**And** the KML file content matches the original uploaded file

#### Scenario: Download route with updated content

**Given** a route was uploaded as "original.kml"
**And** the route has been modified server-side (e.g., waypoint metadata added)
**When** the user downloads the route
**Then** the downloaded KML file reflects the current state
**And** includes any server-side modifications

### Requirement: React Query Integration

The system SHALL use TanStack React Query hooks for all route API operations with automatic cache invalidation and optimistic updates.

#### Scenario: Route list caching

**Given** the Route Manager page has loaded
**And** the route list has been fetched
**When** the user navigates away and returns to the page
**Then** the cached route list is displayed immediately
**And** a background refresh is triggered to check for updates
**And** if new routes exist, the list updates automatically

#### Scenario: Cache invalidation on route upload

**Given** the user uploads a new route
**When** the upload succeeds
**Then** the routes cache is invalidated
**And** the route list automatically refetches
**And** the new route appears in the list without requiring a page refresh

#### Scenario: Cache invalidation on route deletion

**Given** a route is deleted
**When** the deletion succeeds
**Then** the routes cache is invalidated
**And** the route list automatically refetches
**And** the deleted route is removed from the list

#### Scenario: Cache invalidation on route activation

**Given** a route is activated
**When** the activation succeeds
**Then** both the routes cache and POI cache are invalidated
**And** the route list refetches to show updated active status
**And** the POI list refetches to show updated POI projections

### Requirement: Loading States and Error Handling

The system SHALL provide clear loading indicators and error messages for all route operations.

#### Scenario: Display loading state during upload

**Given** the user is uploading a large KML file
**When** the upload is in progress
**Then** a loading spinner is displayed in the upload dialog
**And** the "Upload" button is disabled
**And** a progress message shows "Uploading route..."

#### Scenario: Display error on network failure

**Given** the user attempts to activate a route
**And** the network request fails with a 500 error
**When** the error occurs
**Then** an error message is displayed: "Failed to activate route. Please try again."
**And** the route remains in its previous state
**And** the error message includes a "Retry" button

#### Scenario: Display error on API validation failure

**Given** the user uploads a KML file
**And** the API returns a 400 error with message "Route must have at least 2 points"
**When** the error occurs
**Then** the error message "Route must have at least 2 points" is displayed in the upload dialog
**And** the user can correct the file and retry

### Requirement: Responsive UI Design

The system SHALL provide a responsive layout that adapts to different screen sizes including mobile, tablet, and desktop.

#### Scenario: Desktop layout

**Given** the user accesses the Route Manager on a desktop browser (width >= 1024px)
**When** the page loads
**Then** the split-pane layout is displayed side-by-side
**And** the route list occupies 40% width
**And** the route detail view occupies 60% width

#### Scenario: Mobile layout

**Given** the user accesses the Route Manager on a mobile browser (width < 768px)
**When** the page loads
**Then** the route list is displayed full-width
**And** the route detail view is hidden
**When** the user selects a route
**Then** the detail view slides in full-screen
**And** a "Back" button allows returning to the list

### Requirement: TypeScript Type Safety

The system SHALL use TypeScript interfaces for all route data structures with strict type checking.

#### Scenario: Route service methods are type-safe

**Given** the route service is imported in a component
**When** calling `routesApi.uploadRoute(file)`
**Then** TypeScript validates that `file` is of type `File`
**And** the return type is `Promise<Route>`
**And** attempting to pass invalid arguments causes a compile error

#### Scenario: React Query hooks provide typed data

**Given** a component uses `const { data } = useRoutes()`
**Then** TypeScript infers `data` as `Route[] | undefined`
**And** accessing `data[0].point_count` is type-safe
**And** accessing `data[0].invalid_field` causes a TypeScript error

### Requirement: Accessibility

The system SHALL follow accessibility best practices including ARIA labels, keyboard navigation, and screen reader support.

#### Scenario: Keyboard navigation in route list

**Given** the user is on the Route Manager page
**When** the user presses Tab key
**Then** focus moves sequentially through interactive elements
**And** the focused route row is visually highlighted
**When** the user presses Enter on a focused route row
**Then** the route detail view opens for that route

#### Scenario: Screen reader support

**Given** a screen reader user is on the Route Manager page
**When** the route list is announced
**Then** each route is announced with its name and active status
**And** action buttons include ARIA labels (e.g., "Activate route-alpha", "Delete route-beta")
**And** loading states announce "Loading routes..." or "Uploading route..."
