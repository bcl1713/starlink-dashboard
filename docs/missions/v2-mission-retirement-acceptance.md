# V2 Mission Retirement Acceptance Contract

## Scope

This contract defines the V2 product evidence consumed by the acceptance
platform. It names the product services, public controls, deterministic KML
asset, and visible operator journey. Platform operations, provisioning, and
execution mechanics are documented separately in
[Acceptance Platform Operations](../operations/acceptance-platform.md).

## Services and public controls

The V2 contract scopes the deployed product to these services:

- `starlink-location`
- `mission-planner`

The acceptance lane verifies these public controls through the deployed product:

- Backend health: `/health` returns 200.
- Mission Planner: `/` returns 200.
- Retired legacy collection: `/api/missions` returns 404.
- Retired legacy item: `/api/missions/test` returns 404.
- V2 mission collection: `/api/v2/missions` returns 200.

The legacy paths are intentionally unavailable. The supported activation route
is `POST /api/v2/missions/{mission_id}/legs/{leg_id}/activate`.

## Deterministic route asset

The journey uploads the tracked asset
[`v2-activation-route.kml`](./acceptance-assets/v2-activation-route.kml). It
contains the V2 acceptance route used to prove that activation binds the active
leg to the expected route and points of interest.

## Visible operator journey

The product journey is performed through the public interface, not by creating
pre-existing state or navigating directly to a hidden state:

1. Open Mission Planner and select **Create New Mission**.
2. Enter a mission name and select **Create Mission**.
3. On the mission detail view, select **Add Leg**.
4. Select **Upload KML**, upload `v2-activation-route.kml`, then select
   **Add Leg** to save the route-bound leg.
5. Select **Activate** and observe a successful activation response.
6. Navigate through the visible **Overview** control.
7. Confirm the visible active route context, route name
   `V2 Acceptance Route KAAA-KBBB`, and the **Upcoming POIs** panel with
   separate visible body rows for `KAAA` and `KBBB` (at least two POI rows).

Upcoming POI visibility derives from active-route position; ETA remains
anticipated/estimated metadata. Before planned departure, anticipated ETA is
calendar-based. After a missed planned departure but before actual departure,
planned route durations are re-anchored at now. Once in flight, ETA is estimated
from the current route position; POI visibility remains route-relative.

The journey records a pre-journey and post-journey visual state. A successful
final product result requires the public controls and this visible journey; a
successful endpoint response alone does not prove that the active route context
is visible to an operator.

## Evidence meaning

The V2 contract supplies product observations to the platform evidence owner.
The platform classifies the strength of the result, seals the evidence, and
performs cleanup. A non-final platform result does not establish V2 final
acceptance.
