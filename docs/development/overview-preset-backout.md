# Overview Preset Backout

Issue #426 adds `next_flight_events_only` to shared settings and saved preset
bundles. Before reverting its backend, prepare the settings file for the older
strict preset validator. Reverting code alone can make preset reads and saves
unavailable after Normal, Communications or Weather has been saved by this
build.

1. Stop the application so settings cannot change during preparation.
2. Preserve the complete current Overview settings file as a backup, including
   its ownership and permissions. Keep this feature's source checkout available
   for the preparation command.
3. Prepare a separate file, substituting the actual persistent settings path:

   ```sh
   python3 tools/overview_preset_backout.py \
     --input /path/to/overview-links.json \
     --output /path/to/overview-links.pre-426.json
   ```

4. Review the prepared file against the backup. The command removes only
   `next_flight_events_only` at the top level and inside saved preset settings.
   It preserves preset names, versions, other switches, weather visibility and
   unrelated fields. The Customer bundle remains saved for future use; the older
   application ignores that additional slot. The input is never changed, and an
   existing output is never overwritten.
5. Give the prepared file the original file's ownership/permissions, replace the
   active file while the application remains stopped, revert the feature, then
   restart. Verify preset reads and a Normal preset application. Retain the
   original backup to restore flight-only choices if the feature is reapplied.

No Operator database migration or acknowledgment deletion is required. API-only
advisory classification is excluded from persisted event JSON. Existing POI IDs,
user names and immutable historical records remain intact.
