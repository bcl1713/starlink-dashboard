# export-performance Specification

## Purpose
TBD - created by archiving change refactor-export-logic. Update Purpose after archive.
## Requirements
### Requirement: PPTX Generation Code Consolidation

PowerPoint export logic MUST be extracted into reusable functions to eliminate
duplication between per-leg and mission-level export paths.

#### Scenario: Single leg PPTX export uses shared builder

**Given** a mission leg with timeline data and route information
**When** user exports the leg as PowerPoint via `/api/v2/missions/{leg_id}/export`
**Then** the export uses `create_pptx_presentation()` from
`app.mission.exporter.pptx_builder`
**And** the generated PPTX contains identical slides to pre-refactor behavior
**And** slide count, formatting, and content match the baseline

#### Scenario: Combined mission PPTX export uses shared builder

**Given** a multi-leg mission with 2 legs
**When** user exports the mission as PowerPoint via
`/api/v2/missions/{mission_id}/export`
**Then** the export uses `create_pptx_presentation()` for each leg
**And** slides are combined into a single presentation
**And** the combined PPTX matches pre-refactor structure and formatting
**And** no "Failed to generate PPTX" errors appear in logs

#### Scenario: PPTX builder generates consistent output

**Given** the same mission leg timeline data
**When** PPTX is generated via single-leg export endpoint
**And** PPTX is also generated as part of mission-level export
**Then** both outputs produce identical slide content and formatting
**And** the only difference is the presentation title slide context

### Requirement: Route Map Caching

Route map generation MUST be cached within a single export operation to avoid
redundant expensive rendering when the same route appears in multiple export
artifacts.

#### Scenario: Map cached across export artifacts for same leg

**Given** a mission leg with route "Leg 1 Rev 1"
**When** the system generates exports (XLSX, PPTX, PDF) for the leg
**Then** `_generate_route_map()` is called exactly once for this route
**And** subsequent export artifacts reuse the cached map bytes
**And** logs show "Map generation - Route has 42 valid points" once per unique
route
**And** total export time is reduced by 50%+ compared to pre-refactor

#### Scenario: Map cache scoped to single export operation

**Given** a mission export operation in progress
**When** route maps are generated and cached
**And** the export operation completes
**Then** the map cache is cleared immediately
**And** subsequent export operations start with an empty cache
**And** no memory leaks occur from persisted cache entries

#### Scenario: Multi-leg mission with repeated routes

**Given** a mission with 3 legs using the same route "Common Route Rev 1"
**When** the mission is exported
**Then** `_generate_route_map()` is called once for "Common Route Rev 1"
**And** all 3 legs reuse the cached map image
**And** logs confirm cache hits: "Using cached map for route Common Route Rev 1"
(implementation detail)

### Requirement: Export Performance Benchmarks

Mission export operations MUST complete within defined time bounds to ensure
acceptable user experience for multi-leg missions.

#### Scenario: Two-leg mission export completes in reasonable time

**Given** a mission with 2 legs, each with unique routes
**When** user initiates full mission export
**Then** the export completes in ≤20 seconds
**And** route map is generated exactly 2 times (once per unique route)
**And** no redundant map generation occurs for per-leg exports within the
package

#### Scenario: Five-leg mission export scales efficiently

**Given** a mission with 5 legs, each with unique routes
**When** user initiates full mission export
**Then** the export completes in ≤35 seconds
**And** route map is generated exactly 5 times (once per unique route)
**And** export time scales linearly with leg count, not exponentially

### Requirement: Export Logging Clarity

Export operations MUST log cache hits/misses and generation events to support
debugging and performance monitoring.

#### Scenario: Cache hit logged for reused map

**Given** a mission export operation with map caching enabled
**When** a route map is requested for a route already in cache
**Then** logs contain "Cache hit for route {route_id}" at INFO level
**And** no "Map generation - Route has N points" message appears
**And** `_generate_route_map()` is not called

#### Scenario: Cache miss logged for new map

**Given** a mission export operation with map caching enabled
**When** a route map is requested for a route not in cache
**Then** logs contain "Cache miss for route {route_id}, generating map" at INFO
level
**And** logs contain "Map generation - Route has N points" message
**And** the generated map is stored in cache for subsequent use

