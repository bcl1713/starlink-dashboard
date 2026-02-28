## ADDED Requirements

### Requirement: Mission POI cleanup before regeneration

The system SHALL delete all existing auto-generated POIs for a mission leg before creating new ones during timeline rebuilds. Deletion SHALL match on `route_id`, `mission_id`, and name prefix — without filtering by category. This ensures that POIs created with any category value are properly cleaned up.

#### Scenario: Ka POIs are replaced on timeline rebuild

- **WHEN** a mission timeline is rebuilt for a leg with `route_id = "Leg 1 Rev 2"` and `mission_id = "26-104"`
- **AND** 3 existing Ka POIs exist for that leg (e.g., `CommKa\nExit`, `CommKa\nEnter`, `Ka Transition POR → IOR`)
- **THEN** all 3 existing Ka POIs SHALL be deleted before new Ka POIs are created
- **AND** the resulting POI count for that leg SHALL equal only the newly generated POIs (no duplicates with `-1`, `-2` suffixes)

#### Scenario: X/AAR POIs are replaced on timeline rebuild

- **WHEN** a mission timeline is rebuilt for a leg with existing X-Band and AAR POIs
- **THEN** all existing X/AAR POIs for that leg SHALL be deleted before new ones are created
- **AND** no duplicate POIs SHALL remain

#### Scenario: POIs from other legs are not affected

- **WHEN** a timeline rebuild runs for `route_id = "Leg 1 Rev 2"` with `mission_id = "26-104"`
- **AND** POIs exist for a different leg (`route_id = "Leg 2 Rev 1"`, same mission)
- **THEN** only the POIs matching `route_id = "Leg 1 Rev 2"` SHALL be deleted
- **AND** POIs for `"Leg 2 Rev 1"` SHALL remain unchanged

#### Scenario: User-created POIs are not affected

- **WHEN** a timeline rebuild runs for a mission leg
- **AND** user-created POIs exist with names that do not start with Ka or X/AAR prefixes (e.g., `"CommKa"`, `"Ka Transition"`, `"Ka Swap"`, `"X-Band"`, `"AAR"`)
- **THEN** those user-created POIs SHALL NOT be deleted
