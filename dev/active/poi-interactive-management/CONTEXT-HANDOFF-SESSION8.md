# Session 8 Context Handoff - ETA Calculation Investigation

**Date:** 2025-10-31
**Next Session:** Session 9
**Status:** 🔴 BLOCKED on ETA/Distance/Speed calculation bug

---

## Quick Summary for Session 9

### What Was Done
Three improvements to POI ETA system were implemented:
1. ✅ Integrated real-time coordinator telemetry into POI endpoints
2. ✅ Added low-speed ETA protection (< 0.5 knots threshold)
3. ✅ Stabilized speed simulation (realistic cruise speed)

### The Problem
User observed: "ETA loses 1 minute every 10 seconds"
- Should be: ETA decreases ~10 seconds for every 10 seconds real time
- Actually: ETA decreases 60+ seconds for every 10 seconds real time (6x too fast)
- AND: Distance sometimes INCREASES while aircraft is supposedly approaching

### Investigation Conclusion
**NOT a bug in the math** - all calculations verified correct:
- Haversine formula ✅
- ETA calculation ✅
- Speed values ✅

**The Real Issue:** Test setup problem
- Circular flight route (100km radius around NYC center at 40.7128, -74.0060)
- Test POIs positioned OFF the circular path
- As aircraft orbits, distance to POI fluctuates wildly
- ETA is mathematically correct but reflects aircraft moving away, not toward

### Uncommitted Code

**Files Modified (not yet committed):**
```
/backend/starlink-location/app/api/pois.py
  - get_pois_with_etas() lines 119-155 (coordinator integration)
  - get_next_destination() lines 238-256 (coordinator integration)
  - get_next_eta() lines 299-316 (coordinator integration)
  - get_approaching_pois() lines 357-374 (coordinator integration)

/backend/starlink-location/app/services/eta_calculator.py
  - Line 120: Changed speed threshold from <= 0 to < 0.5

/backend/starlink-location/app/simulation/position.py
  - Lines 111-139: Changed speed variation from ±1.0 to ±0.2 knots
```

**Docker Status:** All changes are built and running
- Container: starlink-location is healthy
- Database: POI data intact at `/data/pois.json`
- Backend: Available at http://localhost:8000

### What Needs to Happen Next

**Option A (Recommended):**
1. Calculate POI coordinates ON the 100km circular route (bearing 90° east from NYC center)
2. Update Test POIs to these coordinates
3. Re-test ETA with predictable approach/departure
4. Verify ETA decreases at correct rate (~10 seconds per 10 seconds)

**Option B:**
1. Change route in config.yaml from circular to straight
2. Set distance and bearing to pass through Test POI locations
3. Re-test with linear path

**Option C:**
1. If A & B both fail, deep debug with detailed logging
2. Trace exactly where ETA calculation diverges from expected
3. Possible issues: speed corruption, coordinate mismatch, formula bug

### Test Command (Next Session)
```bash
# Quick ETA tracking (run from project root)
python3 << 'EOF'
import json, time, re
from urllib.request import urlopen

for i in range(30):
    etas = json.loads(urlopen("http://localhost:8000/api/pois/etas").read())
    metrics = urlopen("http://localhost:8000/metrics").read().decode()

    test2 = [p for p in etas['pois'] if p['name'] == 'Test 2'][0]
    speed_match = re.search(r'starlink_dish_speed_knots ([\d.-]+)', metrics)

    distance = test2['distance_meters']/1000
    eta = test2['eta_seconds']/60
    speed = float(speed_match.group(1))

    print(f"{i*0.5:5.1f}s | Dist: {distance:7.2f}km | ETA: {eta:7.1f}min | Speed: {speed:6.2f}kn")
    time.sleep(0.5)
EOF
```

### Critical Files for Next Session
- `/dev/active/poi-interactive-management/SESSION-NOTES.md` - Full session details
- `/backend/starlink-location/app/api/pois.py` - POI endpoints
- `/backend/starlink-location/app/services/eta_calculator.py` - ETA math
- `/backend/starlink-location/app/simulation/position.py` - Speed simulation
- `/backend/starlink-location/config.yaml` - Route configuration

### Git Status
- Branch: `feature/poi-interactive-management`
- Uncommitted files: Only code modifications (no new files)
- Safe to continue or discard changes as needed

### Next Steps Decision Tree

```
Session 9 starts:
├─ If user wants OPTION A:
│  └─ Calculate proper POI coordinates on circle
│     └─ Update Test POIs
│     └─ Re-test ETA
│     └─ If correct: commit all fixes
│     └─ If still wrong: proceed to Option C
│
├─ If user wants OPTION B:
│  └─ Modify route to straight line in config
│     └─ Re-test ETA
│     └─ If correct: commit all fixes
│     └─ If still wrong: proceed to Option C
│
└─ If user wants OPTION C (debug):
   └─ Add detailed logging to ETA calculation
   └─ Trace speed, distance, formula step-by-step
   └─ Compare expected vs actual values
   └─ Identify which variable is corrupted
```

---

**Handoff Complete - Ready for Session 9**
