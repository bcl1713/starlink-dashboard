# map-label-layout Specification

## Purpose
TBD - created by syncing change fix-pptx-label-overlap. Update Purpose after archive.

## Requirements

### Requirement: Automatic label collision avoidance

Route map POI labels SHALL be automatically repositioned to avoid overlapping. The system MUST use force-directed repulsion (via the `adjustText` library) to resolve label collisions while keeping non-colliding labels close to their markers.

All label types (departure, arrival, mission event POIs) MUST participate in the same collision avoidance pass so that cross-type overlaps are resolved.

#### Scenario: Labels on well-spaced markers remain near their markers

- **WHEN** a route map is generated with POI markers that are far apart (no label bounding boxes overlap)
- **THEN** each label SHALL remain positioned close to its marker
- **AND** no leader lines SHALL be drawn

#### Scenario: Labels on close markers are repositioned to avoid overlap

- **WHEN** a route map is generated with two or more POI markers whose labels would overlap at their default positions
- **THEN** the labels SHALL be repositioned so that no two label bounding boxes overlap
- **AND** all label text SHALL be fully readable

#### Scenario: Displaced labels have leader lines

- **WHEN** a label is repositioned away from its marker to avoid a collision
- **THEN** a thin gray leader line SHALL connect the label to its marker
- **AND** the leader line SHALL use arrow style pointing toward the marker

#### Scenario: All label types participate in collision avoidance

- **WHEN** a route map has a departure label, an arrival label, and mission event labels (AAR, Ka outage, satellite swap)
- **THEN** all labels SHALL be included in a single collision avoidance pass
- **AND** departure labels SHALL NOT overlap mission event labels
- **AND** arrival labels SHALL NOT overlap mission event labels

#### Scenario: Many labels in a tight cluster

- **WHEN** a route map has 10+ POI markers clustered in a small geographic area
- **THEN** all labels SHALL still be rendered and readable
- **AND** leader lines SHALL connect displaced labels to their respective markers
- **AND** no labels SHALL be suppressed or hidden
