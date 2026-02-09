# poi-management Specification Delta

## ADDED Requirements

### Requirement: POI Manager Page

The system SHALL provide a dedicated POI Manager page at `/pois` in the React frontend with a split-pane layout showing an interactive map (left, 60%) and POI list with management controls (right, 40%).

#### Scenario: Access POI Manager from navigation

**Given** the user is on any page in the React frontend
**When** the user clicks the "POIs" link in the main navigation bar
**Then** the browser navigates to `/pois`
**And** the POI Manager page loads with the split-pane layout
**And** the left pane displays an interactive Leaflet map
**And** the right pane displays the POI list and filter controls

#### Scenario: View all POIs in list

**Given** the user is on the POI Manager page
**And** 15 POIs exist in the system
**When** the page loads
**Then** the POI list displays all 15 POIs in a table
**And** each row shows: name, coordinates, category, icon, active status, and action buttons
**And** active POIs are indicated with a green badge
**And** inactive POIs are indicated with a gray badge

### Requirement: POI CRUD Operations

The system SHALL provide create, read, update, and delete operations for POIs through the React frontend UI with form validation and confirmation dialogs.

#### Scenario: Create new POI via form

**Given** the user is on the POI Manager page
**When** the user clicks the "Add POI" button
**Then** a modal dialog opens with an empty POI form
**When** the user enters:
- Name: "Refuel Point Alpha"
- Latitude: 34.0522
- Longitude: -118.2437
- Icon: "airport"
- Category: "refuel"
- Description: "Primary refueling location"
**And** clicks "Save"
**Then** a POST request is sent to `/api/pois`
**And** the new POI appears in the POI list
**And** the new POI appears as a marker on the map
**And** the dialog closes
**And** a success message is displayed

#### Scenario: Create POI via map click

**Given** the user is on the POI Manager page
**When** the user clicks the "Click to Place POI" button
**Then** the map enters click mode with a crosshair cursor
**When** the user clicks a location on the map at coordinates (40.7128, -74.0060)
**Then** the POI creation dialog opens
**And** the latitude field is pre-filled with 40.7128
**And** the longitude field is pre-filled with -74.0060
**When** the user enters a name "New York Waypoint" and clicks "Save"
**Then** the POI is created at the clicked coordinates

#### Scenario: Update POI details

**Given** a POI exists with name "Old Name" and category "waypoint"
**When** the user clicks the "Edit" button for that POI
**Then** the POI dialog opens in edit mode with pre-filled fields
**When** the user changes the name to "Updated Name" and category to "landmark"
**And** clicks "Save"
**Then** a PUT request is sent to `/api/pois/{poi_id}`
**And** the POI list updates to show "Updated Name" and "landmark"
**And** the dialog closes

#### Scenario: Delete POI with confirmation

**Given** a POI exists with name "Test POI"
**When** the user clicks the "Delete" button for that POI
**Then** a confirmation dialog appears with message "Are you sure you want to delete 'Test POI'?"
**When** the user clicks "Confirm"
**Then** a DELETE request is sent to `/api/pois/{poi_id}`
**And** the POI is removed from the list
**And** the POI marker is removed from the map

#### Scenario: POI form validation - invalid latitude

**Given** the user is creating a new POI
**When** the user enters latitude 95.0 (invalid, > 90)
**And** attempts to save
**Then** an error message is displayed: "Latitude must be between -90 and 90"
**And** the submit button is disabled
**And** the POI is not created

### Requirement: POI Filtering

The system SHALL provide filtering controls for POIs by route, mission, active status, and category.

#### Scenario: Filter POIs by route

**Given** 10 POIs exist in the system
**And** 3 POIs are associated with route "route-1"
**When** the user selects "route-1" from the route filter dropdown
**Then** the POI list displays only the 3 POIs associated with "route-1"
**And** the map displays only markers for those 3 POIs
**And** the total count updates to "3 POIs"

#### Scenario: Filter POIs by active status

**Given** 15 POIs exist in the system
**And** 8 POIs are active (associated with active route or mission)
**And** 7 POIs are inactive
**When** the user checks the "Active Only" checkbox
**Then** the POI list displays only the 8 active POIs
**And** inactive POIs are hidden from the list and map

#### Scenario: Clear all filters

**Given** the user has applied route and active filters
**And** the POI list shows 3 filtered POIs
**When** the user clicks the "Clear Filters" button
**Then** all filters are reset
**And** the POI list displays all POIs in the system
**And** the map displays all POI markers

### Requirement: Interactive Map Visualization

The system SHALL provide an interactive Leaflet map showing POI markers, active routes, and route projections with support for International Date Line crossing.

#### Scenario: Display POI markers on map

**Given** 5 POIs exist with different icons (marker, airport, city)
**When** the POI Manager page loads
**Then** the map displays 5 markers at the correct coordinates
**And** each marker uses the POI's configured icon
**And** clicking a marker selects the POI in the list
**And** the selected POI row is highlighted

#### Scenario: Display active route on map

**Given** a route is active
**And** 3 POIs are associated with that route
**When** the POI Manager page loads
**Then** the map displays the active route as a line
**And** the map displays the 3 associated POIs as markers
**And** route projection lines are drawn from POIs to their projected points on the route

#### Scenario: Pan to selected POI

**Given** the user is on the POI Manager page
**When** the user clicks a POI row in the list
**Then** the map pans and zooms to center on that POI's marker
**And** the marker is highlighted or pulsed

### Requirement: Real-Time ETA Calculations

The system SHALL display real-time ETA calculations for POIs with dual-mode support (anticipated pre-departure, estimated in-flight) and course status indicators.

#### Scenario: Display ETAs in flight mode

**Given** the system has telemetry data showing current position (35.0, -120.0) and speed 450 knots
**And** flight status is "in_flight"
**And** 3 POIs exist ahead on the route
**When** the POI Manager page loads
**Then** a GET request is sent to `/api/pois/etas` with current position and speed
**And** the POI list displays ETA values for each POI (e.g., "45 min", "1h 20min")
**And** each POI shows eta_type as "estimated" badge
**And** ETA values update every 5 seconds via polling

#### Scenario: Display anticipated ETAs pre-departure

**Given** flight status is "pre_departure"
**And** the route has timing profile with expected departure time
**And** 3 POIs exist on the route with expected arrival times
**When** the POI Manager page loads
**Then** the POI list displays anticipated ETA values based on flight plan
**And** each POI shows eta_type as "anticipated" badge
**And** a countdown timer shows time until departure

#### Scenario: Display course status

**Given** the system has telemetry showing current heading 90° (East)
**And** a POI exists at bearing 95° from current position
**When** the POI Manager page displays ETAs
**Then** the POI shows course_status as "on_course" (difference < 10°)
**And** the status badge is green
**When** another POI exists at bearing 130°
**Then** that POI shows course_status as "slightly_off" (10-45°)
**And** the status badge is yellow

### Requirement: Route Association and Projection

The system SHALL allow POIs to be associated with routes and display route projection data when a route is active.

#### Scenario: Associate POI with route

**Given** 3 routes exist in the system
**When** the user creates or edits a POI
**Then** the POI form displays a "Route" dropdown
**And** the dropdown contains all available routes plus "(None)" option
**When** the user selects a route and saves
**Then** the POI is associated with that route
**And** the POI's active status depends on whether that route is active

#### Scenario: Display route projection on active route

**Given** a route is active with 100 waypoints
**And** a POI exists 5 km perpendicular from the route
**When** the route is activated
**Then** the system calculates the POI's projection onto the route
**And** the POI list displays:
- Projected coordinates on the route
- Waypoint index of closest route point
- Route progress percentage (0-100%)
**And** the map displays a line from the POI to its projected point
**And** the route-aware status shows "ahead_on_route" if ahead of current position

#### Scenario: Route-aware status for passed POI

**Given** a route is active and in-flight
**And** the current route progress is 60%
**And** a POI is projected at route progress 40%
**When** the POI Manager page displays the POI
**Then** the route-aware status shows "already_passed"
**And** the status badge is gray
**And** the POI is visually de-emphasized in the list

### Requirement: Mission Association

The system SHALL allow POIs to be associated with missions and display active status based on mission state.

#### Scenario: Associate POI with mission

**Given** 2 missions exist: "Mission Alpha" (active) and "Mission Bravo" (inactive)
**When** the user creates a POI
**Then** the POI form displays a "Mission" dropdown with all missions
**When** the user selects "Mission Alpha" and saves
**Then** the POI is associated with "Mission Alpha"
**And** the POI shows as active (green badge) because the mission is active

#### Scenario: POI active status changes with mission

**Given** a POI is associated with "Mission Alpha" (active)
**And** the POI shows as active
**When** "Mission Alpha" is deactivated
**Then** the POI list automatically updates
**And** the POI shows as inactive (gray badge)
**And** the map marker is visually de-emphasized

### Requirement: TypeScript Type Safety

The system SHALL use TypeScript interfaces for all POI data structures with strict type checking.

#### Scenario: POI service methods are type-safe

**Given** the POI service is imported in a component
**When** calling `poisService.createPOI(data)`
**Then** TypeScript validates that `data` matches the `POICreate` interface
**And** the return type is `Promise<POI>`
**And** attempting to pass invalid fields causes a compile error

#### Scenario: React Query hooks provide typed data

**Given** a component uses `const { data } = usePOIs(filters)`
**Then** TypeScript infers `data` as `POI[] | undefined`
**And** accessing `data[0].name` is type-safe
**And** accessing `data[0].invalidField` causes a TypeScript error
