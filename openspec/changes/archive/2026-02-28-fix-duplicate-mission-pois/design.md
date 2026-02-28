## Context

During mission timeline builds, `sync_ka_pois()` and `sync_x_aar_pois()` in `app/mission/timeline_builder/pois.py` delete old auto-generated POIs before creating new ones. The deletion uses `POIManager.delete_leg_pois()` which filters by `route_id`, `mission_id`, optional `categories`, and optional `prefixes`.

The X/AAR path passes `categories=None` and relies on prefix matching alone — this works correctly. The Ka path passes `KA_POI_CATEGORIES = {"mission-ka-transition", "mission-ka-gap-exit", "mission-ka-gap-entry"}`, but all Ka POIs are actually created with category `"mission-event"` (`MISSION_EVENT_CATEGORY`). The category filter never matches, so nothing is deleted.

## Goals / Non-Goals

**Goals:**
- Ka POIs are properly deleted before regeneration, preventing duplicates
- Consistent deletion strategy between Ka and X/AAR sync functions

**Non-Goals:**
- Changing how POI IDs are generated (the `-1`, `-2` suffix logic is a safety net, not the root cause)
- Adding coordinate-based deduplication (unnecessary once deletion works)
- Manually cleaning up existing duplicate POIs (they self-heal on next timeline rebuild)

## Decisions

### Remove category filter from Ka POI deletion

Pass `categories=None` in `sync_ka_pois()` instead of `KA_POI_CATEGORIES`. This matches the pattern already used by `sync_x_aar_pois()`.

**Why not fix the categories instead?** The POIs are created with `"mission-event"` intentionally — it's the shared category for all auto-generated mission POIs. Splitting into sub-categories would add complexity with no benefit since the prefix filter (`"CommKa"`, `"Ka Transition"`, `"Ka Swap"`) is already specific enough to scope deletions correctly.

### Remove unused `KA_POI_CATEGORIES` constant

With the category filter removed from the deletion call, the constant has no remaining references and should be deleted.

## Risks / Trade-offs

- **Over-deletion risk** → Low. The prefix filter restricts deletion to POIs whose names start with `"Ka Coverage Exit"`, `"Ka Coverage Entry"`, `"Ka Transition"`, `"Ka Swap"`, or `"CommKa"`. These are all auto-generated names that users cannot create through the UI.
- **Existing duplicates** → Self-heal. On the next timeline rebuild for any mission, `delete_leg_pois` will match and remove all existing duplicates (including the `-1`, `-2` suffixed ones) before creating fresh POIs.
