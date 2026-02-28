## Why

Mission timeline rebuilds create duplicate POIs because `delete_leg_pois()` fails to match existing POIs before creating new ones. The root cause is a category mismatch: Ka POIs are created with category `"mission-event"` but the deletion filter looks for `"mission-ka-transition"`, `"mission-ka-gap-exit"`, and `"mission-ka-gap-entry"` — categories that no POI actually has. Each rebuild appends duplicates with incrementing ID suffixes (`-1`, `-2`, ...). Mission 26-104 has ~70 POIs when it should have ~4.

## What Changes

- Remove the `KA_POI_CATEGORIES` filter from the Ka POI deletion call so it matches on name prefixes alone (consistent with how X/AAR deletion already works)
- Remove the unused `KA_POI_CATEGORIES` constant

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `poi-management`: Mission-generated POIs must be properly cleaned up before regeneration to prevent duplicates.

## Impact

- **Backend**: `app/mission/timeline_builder/pois.py` — remove category filter from `sync_ka_pois` deletion call
- **Data**: Existing missions with duplicate POIs will self-heal on next timeline rebuild
- **Risk**: Low — prefix filter (`"CommKa"`, `"Ka Transition"`, `"Ka Swap"`) is already specific enough to avoid deleting unrelated POIs
