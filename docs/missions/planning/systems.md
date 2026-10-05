# Communication Systems & Timeline Logic

## Communication Systems Explained

### X-Band (Military Satellite)

**What it is:** Secure military satellite communication; high bandwidth, low
latency.

**Coverage:** Point-to-point (not global). Coverage exists over specific
geographic regions.

**Constraints:** X-band planning requires satellite elevation of **at least
10°** in both normal flight and AAR mode. Elevation below 10° produces an X
line-of-sight warning showing the measured elevation and the 10° minimum in
timeline previews and saved/recomputed timelines, including derived routes.
Exactly 10° satisfies the elevation minimum; azimuth constraints still apply.

Your aircraft also has an **azimuth dead zone** relative to its heading:
135°–225° aft during normal flight. During AAR, the forward 315°–45° cone is
also forbidden. X satellite transitions retain their ±15-minute buffers.

**How it works:**

1. **Nominal:** Satellite is in your antenna's azimuth window AND elevation is
   at least 10°
1. **Degraded:** Satellite is in a forbidden azimuth cone OR elevation is below
   10°
1. **Transition:** Switching from X-1 to X-2 satellite (requires 15 min buffer
   pre/post)
1. **AAR Window:** The forward azimuth cone also applies; the 10° elevation
   minimum remains in effect

**Typical behavior:**

- Continuous availability over continental US
- 15-minute transitions when crossing satellite seams
- Predictable dead zones (same azimuth every orbit)

---

### Ka (CommKa - High Capacity Satellite)

**What it is:** Commercial very-high-bandwidth satellite system; lower latency
than Ku.

**Coverage:** Footprint includes three overlapping satellite regions:

- **AOR** (Atlantic Ocean Region)
- **POR** (Pacific Ocean Region)
- **IOR** (Indian Ocean Region)

**How it works:**

1. **Nominal:** Aircraft is within coverage footprint (fully automatic)
2. **Degraded:** Aircraft crosses from one satellite footprint to another
   (automatic handoff, <1 sec outage)
3. **Coverage Gap:** International Date Line or polar regions (no service)

**Typical behavior:**

- Automatic, no manual intervention
- Coverage transitions are fast and predictable
- International routes may have 20-30 minute gaps

---

### Ku (StarShield - Backup LEO Constellation)

**What it is:** Lower-bandwidth backup constellation; always available globally.

**Coverage:** Global; multiple satellites in view at all times.

**How it works:**

1. **Always nominal** (default state)
2. **Degraded only if:** You manually flag an outage (rare; e.g., known jamming
   zone)

**Typical behavior:**

- No degradation expected
- Acts as fallback if X-Band and Ka both degrade
- Critical system for ensuring crew connectivity

---

## Understanding Timeline Segments

A **timeline segment** is a period of time where communication status is stable.
Segments change when:

- X-Band transition begins or ends
- Ka satellite handoff occurs
- AAR window starts or ends
- Ku outage flag triggers

### Segment Status Logic

Your aircraft communicates via whichever system is available (priority: X-Band >
Ka > Ku). Status reflects how many systems are degraded:

| Systems Down | Label    | Color  | Risk   |
| ------------ | -------- | ------ | ------ |
| 0            | NOMINAL  | Green  | Low    |
| 1            | DEGRADED | Yellow | Medium |
| 2+           | CRITICAL | Red    | High   |

### Reading the Timeline

Example timeline output:

```text
Time              Duration  X-Band          Ka              Ku              Status
09:00:00 - 09:15 15 min    NOMINAL         NOMINAL         NOMINAL         NOMINAL
09:15:00 - 09:30 15 min    DEGRADED (Txn)  NOMINAL         NOMINAL         DEGRADED
09:30:00 - 10:15 45 min    NOMINAL         NOMINAL         NOMINAL         NOMINAL
10:15:00 - 10:20 5 min     NOMINAL         DEGRADED (gap)  NOMINAL         DEGRADED
10:20:00 - 11:00 40 min    NOMINAL         NOMINAL         NOMINAL         NOMINAL
```

**Interpretation:**

- 09:15-09:30: X-Band transitioning to new satellite (crew uses Ka as primary)
- 10:15-10:20: Ka crossing coverage boundary (crew uses X-Band as primary)
- All other times: Multiple systems available (redundancy)
