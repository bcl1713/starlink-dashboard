## MODIFIED Requirements

### Requirement: Route Map Caching

Route map generation MUST be cached within a single export operation to avoid
redundant expensive rendering when the same route appears in multiple export
artifacts.

#### Scenario: Map cached across export artifacts for same leg

**Given** a mission leg with route "Leg 1 Rev 1"
**When** the system generates exports (CSV, PPTX) for the leg
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
