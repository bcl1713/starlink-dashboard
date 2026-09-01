# Mission Package Import

[Back to Mission Planning](mission-planning-guide.md) | [Import upload limit](../setup/configuration/mission-package-upload-limits.md)

---

## Purpose

Use a mission-package ZIP to restore a mission and its legs, route KML files,
and user-authored packaged POIs. The Mission Planner imports the package through:

```text
POST /api/v2/missions/import
```

The uploaded ZIP is limited to 100 MiB. See the [mission-package upload
limit](../setup/configuration/mission-package-upload-limits.md) for proxy and
application-limit details.

Generated timeline-event POIs are not package data. They are rebuilt from the
imported route and mission settings after import, so the archive neither exposes
internal generation provenance nor preserves stale derived events. User-created
POIs, including ones with the same name/category as a generated event, remain
portable.

## Endpoint POIs Restored During Import

For every imported leg whose referenced route is available and has endpoints,
the importer restores exactly two endpoint POIs:

| Role      | Source                       | POI category | Icon      |
| --------- | ---------------------------- | ------------ | --------- |
| Departure | First point in the leg route | `departure`  | `airport` |
| Arrival   | Last point in the leg route  | `arrival`    | `flag`    |

Each restored endpoint POI is associated with both the imported parent mission
and its route. This makes the endpoints available to mission- and route-scoped
POI views without requiring planners to recreate them manually.

The endpoint sync is deliberately narrow: it replaces only endpoint markers
owned by this mission-package import for the same leg, mission, and route. It
does not delete user-created POIs, satellite POIs, or other mission-event POIs.

## Import Result

A successful import returns an object that includes the normal package-import
counts plus `endpoint_pois_restored` and `warnings`.

```json
{
  "success": true,
  "mission_id": "mission-123",
  "mission_name": "Example Mission",
  "leg_count": 1,
  "routes_imported": 1,
  "pois_imported": 0,
  "endpoint_pois_restored": 2,
  "satellites_imported": 0,
  "satellites_updated": 0,
  "warnings": []
}
```

`endpoint_pois_restored` is the number of departure and arrival POIs created
by this import request. A leg with a resolvable route normally contributes `2`.
It can be lower when one or more referenced routes are unavailable or have no
route points.

## Warnings and Operator Action

An import can succeed while returning warnings. Always inspect the `warnings`
array before treating the restored mission as ready for use.

| Warning condition               | Example warning                                                       | Operator action                                                                                                                    |
| ------------------------------- | --------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| Referenced route is unavailable | `Endpoint POIs not restored for leg <leg-id>: route unavailable`      | Confirm that the package contains the leg's expected `routes/<route-id>.kml` file and that it parses successfully, then re-import. |
| Route has no usable endpoints   | `Endpoint POIs not restored for leg <leg-id>: route has no endpoints` | Correct the route KML so it has route points, then re-import.                                                                      |
| Route manager is unavailable    | `Endpoint POIs not restored: route manager unavailable`               | Restore backend route-management availability and retry the import.                                                                |

Route-import and packaged-POI warnings can also appear in the same array. A
nonzero `routes_imported` count alone is not sufficient evidence that endpoint
POIs were restored; use both `endpoint_pois_restored` and `warnings`.

## Re-import and Idempotency

Re-importing the same package is safe for endpoint POIs. For every resolvable
leg, the importer reconciles its two owned endpoint markers and recreates one
departure and one arrival POI at the current route endpoints. The result may
again report `2` restored POIs for that leg; that count describes work performed
by the request, not newly accumulated records.

After a successful re-import, there remains one owned departure POI and one
owned arrival POI per resolvable imported leg. Re-import does not duplicate
those endpoint markers and does not remove unrelated POIs.

## Verification Checklist

After an import:

1. Confirm `success` is `true` and review every entry in `warnings`.
2. Confirm `endpoint_pois_restored` equals two times the number of imported legs
   with resolvable routes and route endpoints.
3. In the POI view, confirm each restored departure and arrival marker belongs
   to the expected mission and route and is at the first and last route point.
4. Re-import a representative package and confirm the same endpoint markers are
   reconciled rather than duplicated, while unrelated POIs remain present.

---

[Back to Mission Planning](mission-planning-guide.md) | [Import upload limit](../setup/configuration/mission-package-upload-limits.md)
