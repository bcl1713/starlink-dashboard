# POI Interactive Management - Best Practices Research

**Last Updated:** 2025-10-30

**Research Source:** Web search compilation from industry leaders (Grafana, Uber, Google Maps, AWS)

---

## Executive Summary

This document compiles industry best practices for implementing the POI Interactive Management feature, based on research from leading companies and open-source projects. The findings validate most of the strategic plan while highlighting several critical considerations and optimizations.

---

## 1. Grafana Geomap & Dynamic Data Best Practices

### Key Findings from Grafana Documentation

#### Data Layer Configuration ✅

**Best Practice:** Use automatic field detection by naming fields `latitude`/`lat` and `longitude`/`lon`/`lng`

**Recommendation for POI Plan:**
```json
// Ensure POI API returns fields with these exact names
{
  "latitude": 40.6413,    // ✅ Grafana auto-detects
  "longitude": -73.7781,   // ✅ Grafana auto-detects
  "name": "JFK Airport"
}
```

**Impact:** Phase 2.2 - No additional configuration needed for location mapping

---

#### Performance Optimization 🔧

**Finding:** "Push work down" to database/API layer before Grafana

**Quote:** *"If you query systems for large records only to filter in Grafana to the few records you really want, performance might get sluggish. Your best bet is to 'push work down' to each data query as much as you can."*

**Recommendation for Phase 1.3:**
```python
# Good: Filter POIs at API level
GET /api/pois/etas?within_distance=100km&category=airport

# Bad: Return all POIs and filter in Grafana
GET /api/pois/etas  # Returns 1000 POIs, Grafana filters to 10
```

**Implementation:**
- Add query parameters to `/api/pois/etas` endpoint:
  - `?max_distance=<meters>` - Only return POIs within distance
  - `?category=<type>` - Filter by category
  - `?limit=<n>` - Limit results to closest N POIs

**Impact:** Critical for performance with 50+ POIs

---

#### Marker Sizing and Customization ✅

**Finding:** Size markers based on data fields with min/max bounds

**Implementation for Phase 2.3:**
```json
{
  "config": {
    "style": {
      "size": {
        "field": "eta_seconds",  // Closer POIs = larger markers
        "mode": "field",
        "min": 8,   // Minimum marker size
        "max": 20   // Maximum marker size
      }
    }
  }
}
```

**Alternative:** Use fixed size (12px) for consistency, rely on color for urgency

---

#### Multiple Data Sources Warning ⚠️

**Finding:** Grafana doesn't support filtering markers from same query by category

**Quote:** *"Grafana currently does not support the ability to filter markers from the same query. You should split data into two separate queries (by category in this case)."*

**Implication for Phase 3:**
- Cannot use single query with Grafana-side filtering
- Must either:
  - **Option A:** Return all POIs in single query, accept no category-based filtering
  - **Option B:** Create separate queries per category (increases query count)

**Recommendation:** Use Option A for simplicity, add API-side category filtering

---

### Performance Benchmarks from QuestDB Blog

**Finding:** Real-time map markers with 1-second refresh are achievable

**Their Setup:**
- QuestDB → Grafana
- Sub-second query responses
- Multiple marker layers updating simultaneously

**Validation:** Our plan's 1-second refresh interval is industry-standard ✅

---

## 2. Grafana Infinity Plugin Best Practices

### JSON API Integration Patterns

#### Backend Parser Recommendation 🔧

**Finding:** Use `backend` parser over `frontend` parser

**Quote:** *"The backend parser as the default parser for new queries is now recommended, though existing queries with frontend parser should work as before."*

**Reason:**
- Supports alerting and recorded queries
- Better for production use
- Required for some advanced features

**Phase 2.1 Update:**
```json
{
  "type": "json",
  "parser": "backend",  // ✅ Use backend parser
  "url": "http://starlink-location:8000/api/pois/etas"
}
```

---

#### JSONPath for Nested Data ✅

**Finding:** Use JSONPath selectors when data is nested

**Example from POI API:**
```json
// If API returns nested structure:
{
  "status": "ok",
  "data": {
    "pois": [ ... ]  // Actual POI array
  }
}

// Use JSONPath root selector:
"root_selector": "$.data.pois"
```

**Current Plan:** POI API returns flat array → No JSONPath needed ✅

---

#### HTTP Headers and Methods 🔧

**Finding:** Infinity now supports:
- Custom HTTP headers
- Methods: GET, POST, PUT, PATCH, DELETE (with flag)
- Accept header auto-set to `application/json`

**Implementation for Phase 5.8 (real-time sync):**
```python
# Backend can accept POST to trigger POI refresh
@app.post("/api/pois/refresh")
async def trigger_poi_refresh():
    # Grafana can call this to force update
    return {"status": "refreshed"}
```

---

#### Pagination Support 🆕

**Finding:** Infinity added pagination support for JSON queries

**Recommendation for Phase 4 (Table View):**
```json
{
  "pagination": {
    "type": "offset",
    "page_param": "page",
    "size_param": "limit"
  }
}
```

**API Endpoint Enhancement:**
```python
GET /api/pois/etas?page=1&limit=20
```

**Impact:** Enables efficient table view with 100+ POIs

---

## 3. Real-Time ETA Calculation Best Practices

### Industry Standards from Uber's DeepETA

#### Hybrid Architecture Pattern 🏆

**Finding:** Uber uses "ETA post-processing" - ML predicts residual between routing engine and reality

**Simplified for POI System:**
```python
# Phase 1: Simple straight-line ETA
eta_simple = distance / current_speed

# Phase 2 (Future): Add corrections
eta_corrected = eta_simple * correction_factor(weather, traffic, historical)
```

**Current Plan:** Start with simple (Phase 1) ✅ - Add ML later (out of scope)

---

#### Caching Strategy 🔧

**Critical Finding:** Cache ETA calculations for frequently accessed routes

**Quote:** *"Set an appropriate TTL (Time-to-Live) for each cached entry based on how dynamic the data is."*

**Implementation for Phase 1.2:**
```python
from functools import lru_cache
from datetime import datetime, timedelta

class ETACalculator:
    def __init__(self):
        self._cache = {}
        self._cache_ttl = timedelta(seconds=5)

    def calculate_eta(self, current_pos, poi, speed):
        cache_key = f"{poi.id}_{current_pos.lat}_{current_pos.lon}"

        # Check cache
        if cache_key in self._cache:
            cached_time, cached_eta = self._cache[cache_key]
            if datetime.now() - cached_time < self._cache_ttl:
                return cached_eta

        # Calculate and cache
        eta = self._haversine_eta(current_pos, poi, speed)
        self._cache[cache_key] = (datetime.now(), eta)
        return eta
```

**Benefits:**
- Reduces CPU load (important for 50+ POIs)
- Smooths ETA display (less jitter)
- 5-second TTL balances accuracy vs. performance

---

#### Geospatial Optimization 🔧

**Finding:** Uber quantizes coordinates for O(1) hash lookups

**For POI System:**
```python
# Round coordinates to reduce cache key variations
def quantize_coord(coord, precision=3):
    """Round to 3 decimal places (~100m accuracy)"""
    return round(coord, precision)

cache_key = (
    poi.id,
    quantize_coord(current_pos.lat),
    quantize_coord(current_pos.lon)
)
```

**Impact:** Dramatically reduces cache misses, improves performance

---

#### Data Integration Priority 📊

**Finding:** ETA accuracy depends on data sources in this order:

1. **High-frequency GPS** (1Hz minimum) ✅ - We have this
2. **Real-time traffic** - N/A for aviation
3. **Historical patterns** - Future enhancement
4. **Weather conditions** - Future enhancement

**Current Plan Status:** Sufficient for Phase 1 ✅

---

#### Geographic Granularity 🎯

**Finding:** Two approaches exist:
- **Segment-based:** Predict each road segment, then aggregate
- **Route-based:** Use origin/destination for trip-level prediction

**POI System Decision:** Route-based (straight-line) ✅
- Simpler for aviation use case
- No road network involved
- Great-circle distance is appropriate

---

### Aviation-Specific ETA Calculations

#### Course Correction Algorithms ✈️

**Finding from Aviation Navigation:**

**1:60 Rule:** For every 1° off course, you'll be 1 mile off track after 60 miles

**Double Track Method:** At halfway point, double the time difference observed

**Opening/Closing Angle:** Assess angle off track and adjust heading accordingly

**Implementation for Phase 1.6:**
```python
def calculate_bearing_to_poi(current_pos, poi):
    """Calculate bearing from current position to POI"""
    lat1, lon1 = radians(current_pos.lat), radians(current_pos.lon)
    lat2, lon2 = radians(poi.latitude), radians(poi.longitude)

    dlon = lon2 - lon1
    x = sin(dlon) * cos(lat2)
    y = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon)
    bearing = degrees(atan2(x, y))

    return (bearing + 360) % 360  # Normalize to 0-360°

def calculate_course_difference(current_heading, bearing_to_poi):
    """Calculate difference between current heading and bearing to POI"""
    diff = abs(current_heading - bearing_to_poi)
    if diff > 180:
        diff = 360 - diff
    return diff

def assess_poi_status(current_heading, bearing_to_poi, distance_nm):
    """Determine if POI is on course, off track, or behind"""
    course_diff = calculate_course_difference(current_heading, bearing_to_poi)

    if course_diff < 45:
        return "on_course", f"{distance_nm:.1f} NM ahead"
    elif course_diff < 90:
        return "slightly_off", f"{distance_nm:.1f} NM off track"
    elif course_diff < 135:
        return "off_track", f"{distance_nm:.1f} NM perpendicular"
    else:
        return "behind", f"{distance_nm:.1f} NM behind"
```

**Enhancement for Phase 3.4 (Tooltips):**
```
Tooltip Display:
├─ JFK Airport
├─ ETA: 15 minutes (on course)
├─ Distance: 23.5 NM
├─ Bearing: 125° (SE)
└─ Course Correction: -5° (turn right slightly)
```

---

## 4. Prometheus Metrics & Cardinality Best Practices

### Critical Cardinality Findings ⚠️

#### The "10 Rule" Warning

**Finding:** Prometheus recommends max 10 label value combinations per metric

**Quote:** *"As a general rule of thumb, avoid having any metric whose cardinality on a /metrics could potentially go over 10 due to growth in label values."*

**Current POI Plan Impact:**
```python
# Current approach (Phase 1.2):
starlink_eta_poi_seconds{name="JFK Airport"} 450
starlink_eta_poi_seconds{name="LAX"} 1200
# ... 50 POIs = 50 time series ⚠️ Approaching limit
```

**Risk:** With 50+ POIs, we're at 5x the recommended limit

---

#### Mitigation Strategy 🔧

**Option 1: Limit POI Count (Easiest)**
```python
# In POI Manager
MAX_POIS = 20  # Stay well under cardinality limit
```

**Option 2: Use Aggregated Metrics (Better)**
```python
# Single metric with aggregation
starlink_pois_total 15
starlink_pois_within_10min 3
starlink_pois_within_1hour 7

# Individual POI data via API only (not Prometheus)
GET /api/pois/etas  # Returns all POI ETAs
```

**Option 3: Metric Relabeling (Advanced)**
```yaml
# prometheus.yml
metric_relabel_configs:
  - source_labels: [name]
    regex: '.*'
    target_label: poi_category
    replacement: 'all'  # Collapse all POI names to single label
```

**Recommendation for Phase 1.3:**
- **Primary data source:** `/api/pois/etas` endpoint (JSON)
- **Prometheus metrics:** Only summary stats (Option 2)
- **Benefit:** Unlimited POIs, no cardinality issues

---

#### Scrape Interval Optimization 🔧

**Finding:** Default Prometheus scrape is 15s (4 data points/minute)

**Quote:** *"If this frequency is not required, the default configuration can result in more data being stored than was forecasted."*

**POI System Decision:**
```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'starlink-location'
    scrape_interval: 5s  # Faster than default for real-time feel
    static_configs:
      - targets: ['starlink-location:8000']
```

**Trade-off:**
- 5s interval: 12 data points/minute (3x default) → More real-time
- 15s interval: 4 data points/minute → Less storage

**Recommendation:** Keep 5s for real-time dashboard, acceptable storage cost

---

### Metric Naming Best Practices ✅

**Finding:** Prometheus has strict naming conventions

**Current Plan Compliance:**
```python
# ✅ Good: Follows conventions
starlink_eta_poi_seconds        # Unit in suffix
starlink_distance_to_poi_meters # Unit in suffix
starlink_dish_latitude_degrees  # Unit in suffix

# ❌ Bad: Would violate conventions
eta_to_poi_seconds              # Missing namespace prefix
poi_distance                    # Missing unit
starlinkEtaPoi                  # camelCase not allowed
```

**Current Plan Status:** ✅ Already compliant

---

## 5. FastAPI WebSocket Real-Time Updates

### Connection Manager Pattern 🏆

**Industry Standard Pattern:**
```python
from fastapi import WebSocket
from typing import List

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                # Connection closed, remove it
                self.active_connections.remove(connection)

manager = ConnectionManager()

@app.websocket("/ws/pois")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except:
        manager.disconnect(websocket)
```

---

### Database Integration Patterns

**Pattern 1: Postgres LISTEN/NOTIFY (If using DB)**
```python
# Not applicable - we use JSON file storage
```

**Pattern 2: File Watcher (For JSON storage) 🔧**
```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class POIFileHandler(FileSystemEventHandler):
    def __init__(self, manager: ConnectionManager):
        self.manager = manager

    def on_modified(self, event):
        if event.src_path.endswith('pois.json'):
            # File changed, broadcast update
            pois = load_pois_from_file()
            asyncio.create_task(
                self.manager.broadcast({
                    "type": "pois_updated",
                    "pois": pois
                })
            )

# Start watcher
observer = Observer()
observer.schedule(POIFileHandler(manager), path='/data', recursive=False)
observer.start()
```

**Phase 5.8 Implementation:** Use file watcher + WebSocket broadcast

---

### Alternative: Server-Sent Events (SSE) 🔧

**Finding:** SSE simpler than WebSocket for one-way updates

**Comparison:**
- **WebSocket:** Bidirectional, more complex, full-duplex
- **SSE:** Unidirectional (server → client), simpler, auto-reconnect

**For POI System:**
```python
from fastapi.responses import StreamingResponse

async def poi_updates_stream():
    while True:
        # Wait for POI changes
        await poi_change_event.wait()
        pois = get_current_pois()
        yield f"data: {json.dumps(pois)}\n\n"
        poi_change_event.clear()

@app.get("/api/pois/stream")
async def stream_poi_updates():
    return StreamingResponse(
        poi_updates_stream(),
        media_type="text/event-stream"
    )
```

**Recommendation for Phase 5.8:**
- **Start with:** Manual refresh button (simplest)
- **Upgrade to:** SSE if needed (easier than WebSocket)
- **Future:** WebSocket for bidirectional (if needed)

---

## 6. Grafana Dashboard Performance Optimization

### Refresh Rate Best Practices 🔧

**Critical Finding:** Aggressive refresh rates harm performance

**Quote:** *"For not frequently changing data, set refresh to 1-5 minutes, not 5 seconds unless you like lag."*

**POI System Decision Matrix:**

| Panel | Data Volatility | Recommended Refresh |
|-------|----------------|---------------------|
| Current Position | Very High | 1s ✅ |
| POI Markers | Low (POIs rarely change) | 30s → 1min |
| POI Table with ETA | High (ETA changes) | 5s ✅ |
| POI Management UI | On-demand | Manual only |

**Phase 2-4 Optimization:**
```json
{
  "refresh": "30s",  // POI marker layer - slower refresh OK
  "panels": [
    {
      "id": 1,
      "type": "geomap",
      "title": "Current Position",
      // Position layer queries every 1s
      // POI layer queries every 30s (separate query)
    },
    {
      "id": 2,
      "type": "table",
      "title": "POI ETAs",
      "refresh": "5s"  // Table needs real-time ETA updates
    }
  ]
}
```

---

### Query Consolidation 🔧

**Finding:** Consolidate related metrics into single queries

**Quote:** *"Consolidate related metrics into single panels using multi-metric queries to reduce the total request count."*

**Implementation for Phase 3:**
```
# ❌ Bad: Multiple queries
Query A: GET /api/pois           (static data)
Query B: GET /api/pois/etas      (ETA data)
Query C: GET /api/pois/distances (distance data)

# ✅ Good: Single consolidated query
Query A: GET /api/pois/etas  (returns POI + ETA + distance + bearing)
```

**API Response Structure:**
```json
[
  {
    "poi_id": "jfk-airport",
    "name": "JFK Airport",
    "latitude": 40.6413,
    "longitude": -73.7781,
    "category": "airport",
    "icon": "airport",
    "eta_seconds": 1234,
    "distance_meters": 45000,
    "bearing_degrees": 125,
    "on_course": true
  }
]
```

**Benefit:** 3 queries → 1 query = 3x faster dashboard load

---

### Recording Rules for Heavy Queries 🔧

**Finding:** Pre-calculate expensive queries in Prometheus

**Quote:** *"Recording rules allow you to add your query to Prometheus and instead of calculating the query for the intended time range on dashboard load, Prometheus calculates this query continuously."*

**Application to POI System:**
```yaml
# prometheus-rules.yml
groups:
  - name: poi_recordings
    interval: 5s
    rules:
      # Pre-calculate closest POI
      - record: poi:closest:eta_seconds
        expr: min(starlink_eta_poi_seconds)

      # Count approaching POIs
      - record: poi:approaching:count
        expr: count(starlink_eta_poi_seconds < 900)  # < 15 min
```

**Benefit:** Complex dashboard queries become instant lookups

**Recommendation:** Phase 6 optimization if dashboard is slow

---

### Dashboard Design: Collapsible Rows 🔧

**Finding:** Use collapsible rows to defer loading

**Quote:** *"Rows can be collapsed and should not be loaded until expanded, allowing you to have graphs prepared and easily accessible when needed but not loading all the time."*

**Phase 4 Enhancement:**
```json
{
  "dashboard": {
    "rows": [
      {
        "title": "Overview",
        "collapsed": false,  // Always visible
        "panels": [ /* map, stats */ ]
      },
      {
        "title": "Detailed POI Table",
        "collapsed": true,   // Load on expand
        "panels": [ /* table with all POIs */ ]
      }
    ]
  }
}
```

---

### Query Caching 🔧

**Finding:** Grafana Cloud offers query result caching

**Quote:** *"After the first person loads the dashboard, all subsequent load times go down to just 1 second with query caching."*

**For Self-Hosted Grafana:**
- Not available by default
- Can implement backend caching (already covered in Section 3)

**API-Level Caching (Phase 1.3):**
```python
from functools import lru_cache

@lru_cache(maxsize=128, ttl=5)
def get_pois_with_etas():
    # Expensive calculation
    return calculate_all_poi_etas()

@app.get("/api/pois/etas")
async def pois_etas_endpoint():
    return get_pois_with_etas()
```

---

## 7. Marker Clustering Best Practices

### When to Use Clustering 🎯

**Finding:** Clustering is for performance, not always better UX

**Quote:** *"Displaying hundreds of POIs on a web map in two dimensions with acceptable usability remains a real challenge. Web practitioners often make excessive use of clustering without successfully resolving issues of perceived performance."*

**POI System Decision:**
- **< 20 POIs:** No clustering needed ✅
- **20-50 POIs:** Optional clustering at low zoom levels
- **50+ POIs:** Clustering recommended

**Current Plan:** Targets < 50 POIs → Clustering optional, not critical

---

### Clustering Algorithm 🔧

**Standard Approach:** Grid-based clustering

**How it works:**
1. Divide map into 60x60 pixel grid squares
2. Group markers in same grid square
3. As user zooms in, grid gets finer, clusters split

**Implementation (If Needed):**
```javascript
// Leaflet.markercluster plugin for POI management UI
var markers = L.markerClusterGroup({
    maxClusterRadius: 60,  // Grid size
    disableClusteringAtZoom: 12  // Show all markers at zoom level 12+
});

pois.forEach(poi => {
    var marker = L.marker([poi.latitude, poi.longitude]);
    markers.addLayer(marker);
});

map.addLayer(markers);
```

**Grafana Geomap:** Clustering not natively supported (as of v11)

**Workaround:** API-side aggregation by geographic region

---

### Alternative to Clustering: Heatmaps 🔧

**Finding:** Heatmaps better for density visualization

**Use Case:** If 100+ POIs in same area

**Implementation:**
```json
{
  "type": "geomap",
  "layers": [
    {
      "type": "heatmap",  // Instead of markers
      "config": {
        "intensity": "eta_seconds",
        "radius": 20
      }
    }
  ]
}
```

**Current Plan:** Stick with markers (< 50 POIs) ✅

---

## 8. JSON File Storage & Concurrency

### File Locking Critical Implementation ⚠️

**Finding:** File locking essential for concurrent access

**Current POI Manager (Phase 1.4 Review):**
```python
# backend/starlink-location/app/services/poi_manager.py

# ⚠️ Current implementation: No file locking!
def _save_pois(self) -> None:
    with open(self.pois_file, "w") as f:
        json.dump(data, f, indent=2)
```

**Risk:** Concurrent writes can corrupt JSON file

---

### Recommended Implementation 🔧

**Use `filelock` library:**

```bash
pip install filelock
```

```python
from filelock import FileLock, Timeout
from pathlib import Path

class POIManager:
    def __init__(self, pois_file: str | Path = "/data/pois.json"):
        self.pois_file = Path(pois_file)
        self.lock_file = Path(str(pois_file) + ".lock")
        self._pois: dict[str, POI] = {}
        self._load_pois()

    def _load_pois(self) -> None:
        """Load POIs from JSON file with shared lock (allows concurrent reads)"""
        lock = FileLock(self.lock_file, timeout=2)
        try:
            with lock.acquire(timeout=2):
                with open(self.pois_file, "r") as f:
                    data = json.load(f)
                # Process data...
        except Timeout:
            logger.error("Failed to acquire read lock on pois.json")
            # Use cached data

    def _save_pois(self) -> None:
        """Save POIs to JSON file with exclusive lock"""
        lock = FileLock(self.lock_file, timeout=5)
        try:
            with lock.acquire(timeout=5):
                # Read existing file (in case other process modified it)
                try:
                    with open(self.pois_file, "r") as f:
                        existing_data = json.load(f)
                except (IOError, json.JSONDecodeError):
                    existing_data = {"pois": {}, "routes": {}}

                # Update pois section
                existing_data["pois"] = self._serialize_pois()

                # Write atomically: write to temp file, then rename
                temp_file = self.pois_file.with_suffix('.tmp')
                with open(temp_file, "w") as f:
                    json.dump(existing_data, f, indent=2)

                # Atomic rename
                temp_file.replace(self.pois_file)

        except Timeout:
            logger.error("Failed to acquire write lock on pois.json")
            raise IOError("Could not save POIs - file locked")
```

**Critical Addition for Phase 1.4:** Add file locking to POIManager

---

### Atomic Write Pattern 🔧

**Best Practice:** Write to temp file, then atomic rename

**Why:**
- If write fails mid-operation, original file intact
- Atomic rename prevents readers from seeing partial data

```python
# ✅ Good: Atomic write
temp_file = "/data/pois.json.tmp"
with open(temp_file, "w") as f:
    json.dump(data, f)
os.replace(temp_file, "/data/pois.json")  # Atomic on Unix/Linux

# ❌ Bad: Direct write (can corrupt)
with open("/data/pois.json", "w") as f:
    json.dump(data, f)  # If crashes here, file corrupted
```

---

### Alternative: Database Migration Path 🔧

**When to migrate from JSON to database:**

**Threshold Indicators:**
- \> 100 POIs
- Multiple concurrent users editing POIs
- Need for POI access history/audit trail
- Complex queries (find POIs in polygon, etc.)

**Migration Path:**
```python
# Phase 1: JSON file (current plan) ✅
# Phase 2: SQLite (single file, no server)
# Phase 3: PostgreSQL (multi-user, transactions)
```

**SQLite Example (Future):**
```python
import sqlite3

class POIManager:
    def __init__(self, db_path="/data/pois.db"):
        self.conn = sqlite3.connect(db_path)
        self._init_db()

    def _init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS pois (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                category TEXT,
                icon TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)

    def create_poi(self, poi_create: POICreate) -> POI:
        # Atomic transaction, no file locking needed
        with self.conn:
            self.conn.execute(
                "INSERT INTO pois VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (poi_id, poi_create.name, ...)
            )
```

**Recommendation:** Stick with JSON for Phase 1, plan SQLite migration if > 50 POIs

---

## 9. REST API Design Best Practices

### HTTP Status Codes ✅

**Current POI API Compliance:**

```python
# backend/starlink-location/app/api/pois.py

# ✅ Already follows best practices:
@router.post("", status_code=status.HTTP_201_CREATED)  # ✅ 201 for creation
@router.delete("/{poi_id}", status_code=status.HTTP_204_NO_CONTENT)  # ✅ 204 for delete
@router.get("/{poi_id}")  # ✅ 404 via HTTPException if not found
```

**Status Code Reference:**
- `200 OK` - GET/PUT successful
- `201 Created` - POST successful ✅
- `204 No Content` - DELETE successful ✅
- `400 Bad Request` - Validation error ✅
- `404 Not Found` - Resource not found ✅
- `422 Unprocessable Entity` - FastAPI validation errors ✅

---

### URL Naming Conventions ✅

**Best Practice:** Plural nouns, no verbs

**Current API:**
```python
# ✅ Good: Plural nouns
GET    /api/pois
POST   /api/pois
GET    /api/pois/{poi_id}
PUT    /api/pois/{poi_id}
DELETE /api/pois/{poi_id}

# ✅ Good: Count as subcollection
GET /api/pois/count/total

# Future: Consider RESTful alternative
GET /api/pois?count_only=true
```

---

### Pagination for Large Collections 🔧

**Finding:** Implement pagination for scalability

**Phase 1.3 Enhancement:**
```python
from typing import Optional

class POIListResponse(BaseModel):
    pois: list[POIResponse]
    total: int
    page: int
    per_page: int
    has_more: bool

@router.get("", response_model=POIListResponse)
async def list_pois(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    route_id: Optional[str] = None
):
    pois = poi_manager.list_pois(route_id=route_id)
    total = len(pois)

    # Paginate
    start = (page - 1) * per_page
    end = start + per_page
    pois_page = pois[start:end]

    return POIListResponse(
        pois=pois_page,
        total=total,
        page=page,
        per_page=per_page,
        has_more=end < total
    )
```

---

### Filtering and Sorting 🔧

**Best Practice:** Use query parameters for filtering

**Phase 1.3 API Enhancement:**
```python
@router.get("/api/pois/etas")
async def get_pois_with_etas(
    category: Optional[str] = Query(None),
    max_distance_km: Optional[float] = Query(None),
    max_eta_minutes: Optional[float] = Query(None),
    sort_by: str = Query("eta", regex="^(eta|distance|name)$"),
    limit: Optional[int] = Query(None, le=100)
):
    pois_with_etas = calculate_all_pois_etas()

    # Filter
    if category:
        pois_with_etas = [p for p in pois_with_etas if p.category == category]
    if max_distance_km:
        pois_with_etas = [p for p in pois_with_etas if p.distance_meters <= max_distance_km * 1000]
    if max_eta_minutes:
        pois_with_etas = [p for p in pois_with_etas if p.eta_seconds <= max_eta_minutes * 60]

    # Sort
    if sort_by == "eta":
        pois_with_etas.sort(key=lambda p: p.eta_seconds)
    elif sort_by == "distance":
        pois_with_etas.sort(key=lambda p: p.distance_meters)
    elif sort_by == "name":
        pois_with_etas.sort(key=lambda p: p.name)

    # Limit
    if limit:
        pois_with_etas = pois_with_etas[:limit]

    return pois_with_etas
```

**Usage Examples:**
```bash
# Get only airports within 50km
GET /api/pois/etas?category=airport&max_distance_km=50

# Get 5 closest POIs by ETA
GET /api/pois/etas?sort_by=eta&limit=5

# Get POIs within 30 minutes
GET /api/pois/etas?max_eta_minutes=30
```

---

## 10. Grafana Iframe Embedding Security

### Configuration Requirements ⚠️

**Critical Finding:** Embedding requires security trade-offs

**Quote:** *"Making configuration changes necessary to support embedding opens your app to cross-site request forgery and clickjacking attacks."*

**Required Settings (grafana.ini):**
```ini
[security]
allow_embedding = true
cookie_samesite = lax  # Required for cookies to work in iframe

[auth]
disable_login_form = false  # Keep login enabled
```

---

### CORS Configuration 🔧

**For cross-origin embedding:**
```ini
[cors]
cors_allow_credentials = true
cors_allowed_origins = http://starlink-location:8000
```

**Important:** Origin must match exactly (including protocol)

---

### Authentication Patterns

**Pattern 1: Proxy-Based Auth (Recommended) 🏆**
```
User → Backend Proxy → Grafana
     │                    ↑
     └─ Auth Check ──────┘
```

**Implementation:**
```python
# backend/starlink-location/app/api/grafana_proxy.py

from fastapi import Request
import httpx

@app.get("/proxy/grafana/{path:path}")
async def proxy_to_grafana(path: str, request: Request):
    # Check user is authenticated (your auth logic)
    if not user_authenticated(request):
        raise HTTPException(401)

    # Forward to Grafana with auth
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://grafana:3000/{path}",
            headers={"Authorization": f"Bearer {GRAFANA_TOKEN}"}
        )
    return response.content
```

---

**Pattern 2: Service Account Token (Simpler, Less Secure)**
```html
<!-- Phase 5.7: Embed Grafana dashboard in POI UI -->
<iframe
  src="http://grafana:3000/d/starlink-fullscreen?auth_token=SERVICE_TOKEN"
  width="100%"
  height="600px"
></iframe>
```

**Warning:** Tokens expire, less secure

---

### Grafana Cloud Limitation ⚠️

**Finding:** Grafana Cloud doesn't support `allow_embedding`

**Quote:** *"If you're using Grafana Cloud, you can't enable allow_embedding, so embedding private, authenticated dashboards isn't supported."*

**POI System:** Self-hosted Grafana → Not affected ✅

---

### Security Recommendations

1. **Use HTTPS** in production (prevents MITM attacks)
2. **Restrict CORS origins** to specific domains (not wildcard `*`)
3. **Implement CSP headers** to prevent clickjacking:
```python
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Content-Security-Policy"] = "frame-ancestors 'self' http://grafana:3000"
    return response
```

4. **Use short-lived tokens** if using Pattern 2
5. **Log all authentication attempts** for audit trail

---

## 11. Leaflet.js Map Integration Best Practices

### Click-to-Place Marker Pattern 🔧

**Standard Implementation:**
```javascript
// Phase 5.6: POI Management UI map

var map = L.map('map').setView([40.7128, -74.0060], 8);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

var marker;  // Single marker for placement

map.on('click', function(e) {
    // Remove previous marker if exists
    if (marker) {
        map.removeLayer(marker);
    }

    // Add new marker at clicked location
    marker = L.marker(e.latlng, {
        draggable: true  // Allow fine-tuning position
    }).addTo(map);

    // Update form fields
    document.getElementById('latitude').value = e.latlng.lat.toFixed(6);
    document.getElementById('longitude').value = e.latlng.lng.toFixed(6);

    // Allow dragging to adjust
    marker.on('dragend', function(e) {
        var position = e.target.getLatLng();
        document.getElementById('latitude').value = position.lat.toFixed(6);
        document.getElementById('longitude').value = position.lng.toFixed(6);
    });
});
```

---

### Form Integration Pattern 🔧

**Bidirectional sync: Map ↔ Form**
```javascript
// Update map when form fields change
document.getElementById('latitude').addEventListener('input', updateMarkerFromForm);
document.getElementById('longitude').addEventListener('input', updateMarkerFromForm);

function updateMarkerFromForm() {
    var lat = parseFloat(document.getElementById('latitude').value);
    var lng = parseFloat(document.getElementById('longitude').value);

    if (!isNaN(lat) && !isNaN(lng)) {
        if (marker) {
            marker.setLatLng([lat, lng]);
        } else {
            marker = L.marker([lat, lng], {draggable: true}).addTo(map);
        }
        map.setView([lat, lng], map.getZoom());
    }
}
```

---

### LayerGroup for Marker Management 🔧

**Best Practice:** Use LayerGroup to manage multiple markers

```javascript
var existingPOIs = L.layerGroup().addTo(map);

// Add existing POIs to map
pois.forEach(poi => {
    L.marker([poi.latitude, poi.longitude])
        .bindPopup(`<b>${poi.name}</b><br>${poi.category}`)
        .addTo(existingPOIs);
});

// Clear all POIs
existingPOIs.clearLayers();
```

---

### Popup with Edit/Delete Actions 🔧

**Pattern for POI management:**
```javascript
function createPOIMarker(poi) {
    var marker = L.marker([poi.latitude, poi.longitude]);

    var popupContent = `
        <div class="poi-popup">
            <h3>${poi.name}</h3>
            <p>${poi.category || 'Uncategorized'}</p>
            <p>${poi.description || ''}</p>
            <button onclick="editPOI('${poi.id}')">Edit</button>
            <button onclick="deletePOI('${poi.id}')">Delete</button>
        </div>
    `;

    marker.bindPopup(popupContent);
    return marker;
}
```

---

## 12. Implementation Priority & Quick Wins

### Critical Path Analysis

Based on research findings, here's the recommended implementation priority:

#### Phase 0: Setup ✅
- Already complete

#### Phase 1: Backend (HIGH PRIORITY) 🚨
**Critical additions from research:**
1. **Task 1.2:** Add file locking to POIManager (data integrity)
2. **Task 1.3:** Implement ETA caching (performance)
3. **Task 1.3:** Add filtering to `/api/pois/etas` (scalability)
4. **Task 1.6:** Enhance bearing calculation with course status

**Estimated Additional Effort:** +1 day

---

#### Phase 2: Grafana Markers (MEDIUM PRIORITY)
**Optimizations from research:**
1. **Task 2.1:** Use backend parser for Infinity plugin
2. **Task 2.2:** Separate queries for position (1s) vs POIs (30s)
3. **Task 2.5:** Add filtering query parameters

**No additional time needed** - integrates into existing tasks

---

#### Phase 3: Tooltips (MEDIUM PRIORITY)
**Enhancement from research:**
1. **Task 3.4:** Add course status to tooltip ("on course", "off track")
2. **Task 3.5:** Consider marker size based on ETA (closer = larger)

**Estimated Additional Effort:** +2 hours

---

#### Phase 4: Table View (LOW PRIORITY)
**Can be done in parallel with Phase 3**
- No critical changes from research
- Add pagination if > 50 POIs expected

---

#### Phase 5: Management UI (MEDIUM-HIGH PRIORITY)
**Security additions from research:**
1. **Task 5.2:** Add authentication to POI management UI
2. **Task 5.6:** Implement Leaflet patterns (click-to-place, draggable)
3. **Task 5.8:** Start with manual refresh (simplest)

**Estimated Additional Effort:** +4 hours (auth)

---

#### Phase 6: Testing (HIGH PRIORITY)
**Add from research:**
1. **Task 6.3:** Test file locking with concurrent API calls
2. **Task 6.2:** Benchmark dashboard with 50 POIs at 1s refresh

**No additional time needed**

---

### Quick Wins (Implement First) 🏆

1. **ETA Caching (Phase 1)** - Massive performance boost, 1-2 hours
2. **Backend Parser (Phase 2)** - 5 minutes, better reliability
3. **Separate Refresh Rates (Phase 2)** - 15 minutes, 30x less load
4. **File Locking (Phase 1)** - 2 hours, prevents corruption
5. **API Filtering (Phase 1)** - 1 hour, essential for scalability

---

## 13. Summary Recommendations

### Adopt Immediately ✅

1. **ETA Caching** with 5-second TTL (Section 3)
2. **File Locking** for POI JSON storage (Section 8)
3. **Consolidated API Endpoint** `/api/pois/etas` with all data (Section 6)
4. **Separate Refresh Rates** for position (1s) vs POIs (30s) (Section 6)
5. **Backend Parser** for Infinity plugin (Section 2)
6. **Query Filtering** by distance, category, ETA (Section 9)
7. **Course Status Calculation** with bearing (Section 3)

---

### Consider for Phase 2 (Future) 🔮

1. **Prometheus Metric Reduction** - Summary stats only (Section 4)
2. **Recording Rules** for expensive queries (Section 6)
3. **WebSocket/SSE** for real-time updates (Section 5)
4. **SQLite Migration** if > 50 POIs (Section 8)
5. **Marker Clustering** if > 50 POIs (Section 7)

---

### Avoid ⛔

1. **Per-POI Prometheus Metrics** with 50+ POIs (cardinality explosion)
2. **1-second refresh for everything** (use 30s for slow-changing data)
3. **Direct iframe embedding without auth** (security risk)
4. **Grafana-side data filtering** (push to API)
5. **Concurrent JSON writes without locking** (data corruption)

---

## 14. Updated Timeline with Research Additions

| Phase | Original Estimate | Research Additions | New Estimate |
|-------|------------------|-------------------|--------------|
| 1 | 2-3 days | +1 day (locking, caching) | 3-4 days |
| 2 | 2-3 days | No change | 2-3 days |
| 3 | 2-3 days | +2 hours (course status) | 2-3 days |
| 4 | 1-2 days | No change | 1-2 days |
| 5 | 4-5 days | +4 hours (auth) | 4-5 days |
| 6 | 2-3 days | No change | 2-3 days |
| 7 | 1 day | No change | 1 day |

**Original Total:** 15-20 days
**Research-Enhanced Total:** 16-22 days (+1-2 days)

**Accelerated (Parallel):** 11-16 days

---

## Conclusion

This research validates the original strategic plan while identifying several critical enhancements:

### Strengths of Original Plan ✅
- Technology choices (Grafana, FastAPI, Infinity) are industry-standard
- Phased approach aligns with best practices
- Timeline estimates are realistic
- Architecture decisions are sound

### Critical Additions from Research 🔧
1. File locking for data integrity
2. ETA caching for performance
3. Separate refresh rates for efficiency
4. Enhanced bearing/course calculations
5. API-side filtering for scalability
6. Security considerations for iframe embedding

### Risk Mitigation ⚠️
- Prometheus cardinality managed via API-first approach
- File corruption prevented via locking
- Performance optimized via caching and refresh rates
- Security enhanced with authentication

**Overall Assessment:** Plan is excellent and production-ready with research enhancements applied.

---

**Document Status:** ✅ Research Complete

**Last Updated:** 2025-10-30

**Next Action:** Apply research findings to implementation (see Section 12)
