# Design: Real-Time Timeline Preview

## Context

Mission leg planning currently requires users to save configurations before
seeing timeline results. The timeline calculation infrastructure exists in
`backend/starlink-location/app/mission/timeline_service.py` (~1,580 lines of
Python geospatial code) and produces:

- Timeline segments with NOMINAL/DEGRADED/CRITICAL status
- Satellite transitions and outages
- X-band/Ku-band azimuth conflicts
- Color-coded visualizations (currently only in export phase)

Users need to see these results in real-time as they adjust satellite
transitions, outage windows, and AAR segments during planning.

## Goals / Non-Goals

**Goals:**

- Real-time timeline preview as users type/change configuration values
- Color-coded route map (green/yellow/red) visible during planning
- Timeline table showing segment details before export
- Manual save workflow (preview doesn't persist until user clicks "Save")
- Sub-second response time for typical routes (<500ms p95)
- Reuse existing timeline calculation infrastructure

**Non-Goals:**

- Offline/client-side timeline calculation
- WebSocket streaming for very long routes
- Undo/redo for configuration changes
- Timeline diff view (saved vs preview)
- Optimistic UI updates before server response

## Decisions

### Decision 1: Server-Side Preview Calculation

**Choice:** Full backend calculation via new preview API endpoint with debounced
requests.

**Why:**

- Timeline calculation requires Python geospatial libraries (shapely, scipy,
  numpy)
- Coverage analysis uses 50MB+ GeoJSON polygon data
- Porting to TypeScript would duplicate ~2,000 lines of code
- Current calculations run in ~100-500ms (acceptable with debouncing)
- Maintenance burden of dual implementations too high

**Alternatives considered:**

- **Client-side TypeScript port:** Rejected due to complexity (geospatial libs,
  coverage data size, maintenance burden)
- **WASM compilation:** Rejected due to Python dependency incompatibilities
  (shapely has C extensions)
- **Simplified client-side preview:** Rejected due to accuracy concerns (users
  need exact results for mission planning)

### Decision 2: Debounced HTTP Requests (500ms)

**Choice:** Debounce user input changes with 500ms delay before triggering
preview calculation.

**Why:**

- Prevents excessive API calls during rapid typing
- 500ms feels responsive to users (sub-second feedback)
- Reduces server load while maintaining real-time feel
- Simple implementation using React useEffect + setTimeout

**Alternatives considered:**

- **WebSocket streaming:** Rejected due to added complexity for <1s
  calculations, no partial result benefit
- **Throttling vs debouncing:** Debouncing chosen because we only care about
  final state after user stops typing
- **Longer delay (1s+):** Rejected as too slow for "real-time" feel
- **Shorter delay (200ms):** Rejected due to excessive server requests

### Decision 3: Dual-State Pattern (Saved vs Preview)

**Choice:** Maintain separate state for saved timeline and preview timeline.

**Why:**

- Allows experimentation without accidental data loss
- Clear visual distinction via "Unsaved" badge
- Easy rollback on cancel (discard preview, keep saved)
- Matches user mental model (preview before commit)

**Data structure:**

```typescript
interface TimelineState {
  savedTimeline: Timeline | null; // From disk (GET /timeline)
  previewTimeline: Timeline | null; // From preview API (ephemeral)
  isCalculating: boolean; // Loading state
  hasUnsavedChanges: boolean; // Config differs from saved
}
```

### Decision 4: Include Route Samples in Preview Response

**Choice:** Extend `MissionLegTimeline` model to optionally include route
samples (lat/lon + timestamp).

**Why:**

- Timeline segments have timestamps but need coordinates for map rendering
- Samples already exist in backend calculation (`RouteSample` objects)
- Marginal bandwidth cost (~50KB for 300 waypoints) acceptable for preview
- Avoids complex frontend interpolation logic

**Implementation:**

```python
class MissionLegTimeline(BaseModel):
    mission_leg_id: str
    created_at: datetime
    segments: list[TimelineSegment]
    advisories: list[dict] = Field(default_factory=list)
    statistics: dict = Field(default_factory=dict)
    samples: list[RouteSample] | None = None  # NEW: optional for preview
```

Preview endpoint calls `build_mission_timeline(include_samples=True)` while
saved timelines call with `include_samples=False` to avoid bloating disk files.

### Decision 5: Color-Coded Polyline Layer

**Choice:** Render timeline segments as separate Leaflet polylines with
status-based colors.

**Why:**

- Leaflet supports multiple polylines with different colors
- Temporal-to-spatial mapping straightforward with route samples
- Existing blue route line remains for reference
- Layer ordering allows colored segments to appear below markers

**Color mapping:**

```typescript
const STATUS_COLORS = {
  NOMINAL: '#2ecc71', // Green - all transports available
  DEGRADED: '#f1c40f', // Yellow - 1 transport impacted or AAR
  CRITICAL: '#e74c3c', // Red - 2+ transports impacted
};
```

## Architecture

### Data Flow

```
User types in config form
  ↓ (instant)
Local React state updates
  ↓ (500ms debounce)
POST /api/v2/missions/{id}/legs/{id}/timeline/preview
  ↓ (100-500ms backend calculation)
Preview timeline returned with segments + samples
  ↓ (instant)
Frontend updates:
  - Color-coded map polylines
  - Timeline table with segment details
  - "Unsaved" badge indicator
  ↓ (user clicks "Save Changes")
PUT /api/v2/missions/{id}/legs/{id}
  ↓ (backend saves + regenerates timeline)
Timeline persisted to disk
  ↓ (instant)
Preview becomes saved state, badge disappears
```

### Component Hierarchy

```
LegDetailPage
├── useTimelinePreview (hook)
│   ├── Debounce logic (500ms)
│   ├── AbortController (request cancellation)
│   └── React Query caching
├── TimingSection
├── LegConfigTabs
│   ├── XBandConfig
│   ├── KaOutageConfig
│   ├── KuOutageConfig
│   └── AARSegmentEditor
├── TimelinePreviewSection (NEW)
│   ├── Collapse/Expand accordion
│   ├── "Unsaved" badge
│   ├── Loading spinner
│   └── TimelineTable (NEW)
│       └── Virtualized rows for large timelines
└── LegMapVisualization
    └── RouteMap
        ├── TileLayer (OpenStreetMap)
        ├── ColorCodedRoute (NEW)
        │   └── Polyline per segment (color-coded)
        ├── RouteLayer (blue route line)
        └── Markers (transitions, waypoints)
```

### API Design

**New Endpoint:**

```
POST /api/v2/missions/{mission_id}/legs/{leg_id}/timeline/preview
```

**Request Body:**

```json
{
  "transports": {
    "initial_x_satellite_id": "X-1",
    "initial_ka_satellite_ids": ["AOR", "POR", "IOR"],
    "x_transitions": [
      { "latitude": 35.5, "longitude": -120.3, "to_satellite": "X-2" }
    ],
    "ka_outages": [
      { "start_time": "2026-01-07T14:00:00Z", "duration_seconds": 3600 }
    ],
    "aar_windows": [{ "start_waypoint": "AAR_START", "end_waypoint": "AAR_END" }],
    "ku_overrides": []
  },
  "adjusted_departure_time": "2026-01-07T12:00:00Z"
}
```

**Response:**

```json
{
  "mission_leg_id": "leg-123",
  "created_at": "2026-01-07T18:30:00Z",
  "segments": [
    {
      "id": "seg-1",
      "start_time": "2026-01-07T12:00:00Z",
      "end_time": "2026-01-07T12:15:00Z",
      "status": "NOMINAL",
      "x_state": "AVAILABLE",
      "ka_state": "AVAILABLE",
      "ku_state": "AVAILABLE",
      "reasons": []
    }
  ],
  "samples": [
    {
      "timestamp": "2026-01-07T12:00:00Z",
      "latitude": 35.5,
      "longitude": -120.3,
      "altitude": 10000,
      "ka_coverage_set": ["AOR"]
    }
  ],
  "advisories": [],
  "statistics": {
    "total_duration_seconds": 14400,
    "degraded_duration_seconds": 1200
  }
}
```

## Risks / Trade-offs

### Risk 1: Backend Load Under Heavy Editing

**Risk:** Users rapidly changing configurations could generate many preview
requests.

**Mitigation:**

- 500ms debounce reduces request frequency
- AbortController cancels in-flight requests when new changes occur
- React Query deduplicates identical requests
- Backend calculation already optimized (~100-500ms)

**Monitoring:** Track preview endpoint call rate and response time via Prometheus
metrics.

### Risk 2: Network Latency for Remote Users

**Risk:** Users on slow connections may experience delays >1s.

**Mitigation:**

- Show "Calculating..." spinner immediately when debounce fires
- Keep preview optional (existing save-then-export workflow still works)
- Consider increasing debounce delay to 750ms if feedback indicates need

**Trade-off accepted:** Real-time preview requires network, no offline mode.

### Risk 3: Large Timeline Rendering Performance

**Risk:** Routes with 500+ waypoints generate 300+ segments, heavy to render.

**Mitigation:**

- Virtualize timeline table (only render visible rows)
- Use React.memo for segment row components
- Leaflet efficiently handles multiple polylines
- Consider coordinate simplification (Douglas-Peucker) if needed

**Performance target:** <200ms for map re-render, <100ms for table render.

### Risk 4: State Synchronization Bugs

**Risk:** Preview state and saved state could get out of sync.

**Mitigation:**

- Single source of truth for config (React state)
- Hash config to detect actual changes before triggering preview
- Clear "Unsaved" indicator when preview differs from saved
- Confirmation dialog on cancel/navigate with unsaved changes

**Testing:** Verify state consistency across save/cancel/navigate scenarios.

## Performance Targets

| Metric                          | Target  | Measurement                                |
| ------------------------------- | ------- | ------------------------------------------ |
| Preview API response time (p95) | <500ms  | Prometheus histogram                       |
| Debounce delay                  | 500ms   | Configurable via hook parameter            |
| Map re-render time              | <200ms  | React DevTools profiler                    |
| Timeline table render time      | <100ms  | React DevTools profiler (300 segments)     |
| Request cancellation latency    | <10ms   | Abort signal propagation                   |
| Preview requests/min (per user) | <6      | (500ms debounce = max 2 req/s during edit) |

## Migration Plan

**No migration required** - this is a new feature with no breaking changes.

**Rollout:**

1. Deploy backend preview endpoint (backward compatible, not used yet)
2. Deploy frontend components (gracefully degrades if endpoint unavailable)
3. Verify preview endpoint metrics in Prometheus
4. Enable feature for all users (no feature flag needed)

**Rollback:**

- Remove frontend preview hook calls (fall back to save-then-export workflow)
- Backend endpoint can remain (harmless if unused)

## Open Questions

### Q1: Should we add a manual "Calculate Preview" button?

**Options:**

- **Auto-calculate only** (current design): Simpler UX, fewer clicks
- **Manual button**: More control, less server load
- **Both**: Auto-calculate with manual refresh button

**Decision:** Start with auto-calculate only. Add manual button if user feedback
indicates need.

### Q2: Should preview timeline be cached for export?

**Options:**

- **Use preview for export** if unchanged: Faster export, no recalculation
- **Always recalculate on export**: Simpler, ensures accuracy

**Decision:** Always recalculate on export (maintains current behavior,
low-risk).

### Q3: Should we show diff between saved and preview timeline?

**Options:**

- **No diff view** (current design): Simpler implementation
- **Show segment diff table**: Helps understand what changed
- **Highlight changed segments on map**: Visual diff

**Decision:** Defer to future iteration. Start with simple "Unsaved" badge
indicator.

## Success Metrics

**User Experience:**

- Time to see timeline preview after config change: <1 second
- User reduces save/export iterations by 50%+ (measured via analytics)
- No reported bugs related to timeline accuracy

**Performance:**

- Preview API p95 response time: <500ms
- Zero timeline calculation failures
- <1% request cancellation rate (indicates debounce is effective)

**Code Quality:**

- All new code has >80% test coverage
- No new ESLint/TypeScript/MyPy errors introduced
- Documentation updated for new API endpoint
