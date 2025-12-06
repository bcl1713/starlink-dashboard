# Communication Systems & Timeline Logic

## Communication Systems Explained

### X-Band (Military Satellite)

**What it is:** Secure military satellite communication; high bandwidth, low
latency.

**Coverage:** Point-to-point (not global). Coverage exists over specific
geographic regions.

**Constraint:** Your aircraft has an **azimuth dead zone**—a direction where the
antenna cannot point at the satellite (typically 90° to 270° from North,
adjustable per mission).

**How it works:**

1. **Nominal:** Satellite is in your antenna's azimuth window AND you have
   line-of-sight
1. **Degraded:** Satellite outside azimuth window (e.g., directly overhead) OR
   aircraft performing aerobatic maneuver
1. **Transition:** Switching from X-1 to X-2 satellite (requires 15 min buffer
   pre/post)
1. **AAR Window:** X-Band goes dark during air refueling (antenna points at
   tanker)

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
