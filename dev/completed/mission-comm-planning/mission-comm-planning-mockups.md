# Mission Communication Planning Mockups

Last Updated: 2025-11-10

These wireframes use **Leg 6 Rev 6 (RKSO → KADW)** as the reference route. Times
below come directly from the timed KML (e.g., KADW takeoff 2025-11-04 23:17:52Z,
-TOC- 23:22:26Z) or representative transition/AAR events along that leg.

## Input GUI Mock (Planner View)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Mission: RKSO → KADW Leg 6 Rev 6          Status: Draft                      │
├──────────────────────────────────────────────────────────────────────────────┤
│ Step 1 • Route & Timing                                                      │
│ [✔] Route file: Leg 6 Rev 6.kml (timing detected, dep 23:17:52Z)             │
│ [Select different route] [Preview map]                                       │
│ Flight clock                                                                 │
│   • Auto-set departure (from KML)  • Manual override [ 23:22Z ▽ ]            │
├──────────────────────────────────────────────────────────────────────────────┤
│ Step 2 • Transport Configuration                                             │
│ X – Fixed Geo Satellites                                                    │
│   Active at takeoff: [SAT X-1 ▽ ]  Azimuth cone: 135°–225° (Std Ops)        │
│   Transition list (planner enters lat/lon + target sat/beam; app             │
│   projects onto route, auto-fills route time & ±15 min degrade)              │
│   ┌────┬──────────┬─────────────┬───────────────────┬────────┬─────────────┐ │
│   │ #  │ Lat      │ Lon         │ Route Time ↑      │ New ID │ Notes       │ │
│   ├────┼──────────┼─────────────┼───────────────────┼────────┼─────────────┤ │
│   │ 1  │ 40.1234N │ 178.5678E   │ 2025-11-05 01:40Z │ X-2   │ Auto az=178°│ │
│   │ 2  │ 43.5000N │ 165.0000E   │ 2025-11-05 05:05Z │ X-3   │ Beam swap   │ │
│   └────┴──────────┴─────────────┴───────────────────┴────────┴─────────────┘ │
│   (↑ Route time computed by backend after projecting the lat/lon onto        │
│   the timed route; POIs generated automatically.)                            │
│   [+ Add transition]  [Import from template]                                 │
│                                                                              │
│ Ka – Global Geo Trio (auto)                                                  │
│   Coverage source: bundled HCX KMZ (change to math if satellite              │
│   differs). Planner sees read-only upcoming transitions + optional           │
│   outage scheduling.                                                         │
│   Current footprint: SAT Ka-West (center 135°E)                              │
│   Next crossover (auto): 2025-11-05 04:10Z near 47N/170E                     │
│   Schedule planned outage? [  ] start  [  ] duration                         │
│                                                                              │
│ Ku – LEO                                                                     │
│   Always-on. Optional maintenance window? [   ] start  [   ] duration        │
├──────────────────────────────────────────────────────────────────────────────┤
│ Step 3 • AAR & Buffers                                                       │
│ AAR events (select start/end from route waypoint dropdowns):                 │
│   ┌────┬────────┬──────────────┬──────────────┬──────────────┐               │
│   │ #  │ Label  │ Start WP ▽   │ End WP ▽     │ Timeline     │               │
│   ├────┼────────┼──────────────┼──────────────┼──────────────┤               │
│   │ 1  │ AAR-1  │ ARIP1 02:55Z │ ARCP1 03:25Z │ auto ±15 min │               │
│   │ 2  │ AAR-2  │ ARIP2 07:10Z │ ARCP2 07:45Z │ auto ±15 min │               │
│   └────┴────────┴──────────────┴──────────────┴──────────────┘               │
│                                                                              │
│ Takeoff/Landing buffers                                                      │
│   • Auto apply ±15 minutes (can override)                                    │
├──────────────────────────────────────────────────────────────────────────────┤
│ Step 4 • Review & Export                                                     │
│ [Compute mission timeline] [Save draft] [Export JSON bundle]                 │
│ After computation:                                                           │
│   - 9 segments nominal, 4 degraded, 1 critical (AAR-2)                       │
│   - Next conflict: X az=182° in 27 min (T+01:47)                            │
│   [Download PDF brief] [Download CSV/XLSX]                                   │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Output PDF Mock (Customer Brief)

**Page 1 – Cover & Summary**

```
[LOGO]  Mission Communication Timeline
Mission: RKSO → KADW  •  Date: 04–05 Nov 2025  •  Leg: 6 Rev 6
Prepared: 2025-11-02 18:00Z by Planner B. Rivera

Transports
- X (Geo Fixed): SAT X-1 → X-2 → X-3 (azimuth-sensitive, ±15 min buffers)
- Ka (Geo Trio): SAT Ka-West → Ka-Central → Ka-East (KMZ footprints)
- Ku (LEO): Continuous, no planned downtime

Key Windows
- Takeoff buffer: 23:02Z–23:32Z (Degraded – runway operations)
- AAR-1: 02:40Z–03:40Z (Critical – refuel, X cone inverted)
- AAR-2: 07:00Z–08:00Z (Critical)
- Landing buffer: 11:10Z–11:40Z

Legend: Nominal (green), Degraded (amber = ≥1 transport out), Critical (red = ≥2 out)
```

**Page 2 – Timeline Table (excerpt)**

| Segment                      | UTC Window  | Eastern Window  | T+ Offset         | Phase   | X                                | Ka                     | Ku  | Status   | Customer Notes                                 |
| ---------------------------- | ----------- | --------------- | ----------------- | ------- | --------------------------------- | ---------------------- | --- | -------- | ---------------------------------------------- |
| Departure buffer             | 23:02–23:32 | 18:02–18:32 EST | T–00:15 → T+00:15 | Takeoff | Locked (manual disable)           | West                   | Up  | Degraded | Standard 15-min ground window                  |
| Climb to TOC                 | 23:32–00:45 | 18:32–19:45 EST | T+00:15 → T+01:58 | Climb   | X-1                              | West                   | Up  | Nominal  | N/A                                            |
| **X Transition 1 buffer**   | 01:25–02:10 | 20:25–21:10 EST | T+02:53 → T+03:38 | Cruise  | Switching X-1→X-2 (manual call) | West                   | Up  | Degraded | Disable X at 01:40Z; buffer ±15 min           |
| Mid-Pacific cruise           | 02:10–02:40 | 21:10–21:40 EST | T+03:38 → T+04:08 | Cruise  | X-2                              | West                   | Up  | Nominal  | N/A                                            |
| **AAR-1 (X cone inverted)** | 02:40–03:40 | 21:40–22:40 EST | T+04:08 → T+05:08 | AAR     | Blocked (az=22°)                  | West                   | Up  | Critical | Suspend all planned comms                      |
| Post AAR recover             | 03:40–04:10 | 22:40–23:10 EST | T+05:08 → T+05:38 | Cruise  | X-2                              | West→Central crossover | Up  | Degraded | Ka footprint overlap narrow – expect 5 min gap |
| **Ka crossover buffer**      | 04:10–04:40 | 23:10–23:40 EST | T+05:38 → T+06:08 | Cruise  | X-2                              | Switching West→Central | Up  | Degraded | Auto degrade ±15 min around footprint switch   |
| ...                          | ...         | ...             | ...               | ...     | ...                               | ...                    | ... | ...      | ...                                            |

**Page 3 – Map & Visual Timeline**

- Full-route geomap with overlays:
  - Aircraft path (Leg 6 Rev 6 GeoJSON)
  - Satellite POIs (X-1, X-2, X-3) + azimuth arcs at time selected
  - Ka coverage polygons (imported KMZ) shaded by active footprint
  - AAR boxes + annotated start/end points
- Timeline lane chart (Nominal/Degraded/Critical) with icons for
  transitions/AAR/landing buffer.

**Appendix – Detailed Events**

- Table listing every X/Ka transition (actual waypoint, projected route time,
  azimuth at switch, ±15 min windows).
- AAR details (track ID, tanker frequency placeholder, inverted cone reminder).
- Export metadata (hash of mission JSON, software version, generation time).

## Ka Coverage Math from KMZ

The provided KMZ polygons allow us to derive transition logic as follows:

1. **Convert KMZ → GeoJSON** using the existing KML tooling; store each
   footprint with metadata (satellite name, longitudinal center, min/max
   latitude).
2. **Sample route timeline** (e.g., every 30–60 seconds) to compute the aircraft
   lat/lon/alt using the timed KML interpolation already in place.
3. **Point-in-polygon test** for each sample against the coverage polygons to
   identify entry/exit timestamps for a given satellite footprint.
4. **Derive recommendations:**
   - When two footprints overlap, compute the midpoint time/location between
     exit and entry to use as the ideal transition (can also bias earlier/later
     via configuration).
   - When no overlap exists (e.g., far north/south), mark the out-of-coverage
     duration as degraded for Ka.
5. **Math fallback:** If KMZ data is missing, approximate coverage using the
   satellite sub-satellite longitude + conservative latitude limits (e.g.,
   derived from elevation angle thresholds). The same sampling framework can
   compute when the geometric elevation drops below the threshold and trigger a
   transition/degraded period.

Because the KMZ already encodes the real beam boundaries, ingesting it provides
the ground truth transition points, while the math fallback keeps things working
when planners only supply satellite orbital slots.
