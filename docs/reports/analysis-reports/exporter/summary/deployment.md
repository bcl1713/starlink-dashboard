# Deployment & Implementation Notes

## Integration Points

### RouteManager Integration

```python
route = route_manager.get_route(mission.route_id)
# Use: route.points (list of Waypoint with lat/lon/expected_arrival_time)
#      route.waypoints (with roles: departure, arrival)
# Files: routes_dir/{route_id}.kml
```

### POIManager Integration

```python
pois = poi_manager.list_pois(route_id=..., mission_id=...)
# POI fields: id, name, latitude, longitude, category, role
# Uses: Mission event POIs (AAR, satellite swaps, Ka transitions)
```

### Storage Integration

```python
mission = load_mission_v2(mission_id)
timeline = load_mission_timeline(leg_id)
# Returns: Pydantic models with full nested structure
```

---

## Recommended Refactoring

See `EXPORTER-refactoring-plan.md` for detailed plan.

**Quick Summary:**

1. Extract pure utilities (formatting, transport display)
2. Separate data processing layer (DataFrames from rendering)
3. Isolate visualization (map, chart generation)
4. Split by format (CSV, XLSX, PDF, PPTX modules)
5. Extract packaging logic
6. Extract combined export logic (lower priority)

**Result:** 2 monolithic files → 16 focused modules

- Each module: Single responsibility, clear dependencies
- Easier to test, modify, and extend
- No regression in functionality or performance

---

## Testing Recommendations

### Unit Tests (Phase 1-2)

- Formatting functions (100% coverage)
- Transport display utilities (100% coverage)
- Data builders (90%+ coverage)
- No mocking needed

### Integration Tests (Phase 3-4)

- Visualization rendering (snapshot tests for PNG)
- Format generation (structure validation)
- Manager integration (mock managers)
- Performance benchmarks

### System Tests (Phase 5-6)

- Archive structure and contents
- Multi-leg export consistency
- End-to-end workflows
- Error handling and recovery

---

## Deployment Notes

### Docker Considerations

- Matplotlib configured for headless mode (Agg backend)
- Cartopy data directory: ~25 MB, mounted as volume
- PNG generation: CPU intensive, consider async processing for large exports

### System Requirements

- RAM: 2+ GB per export job (image buffering)
- CPU: 2+ cores (Cartopy uses threading)
- Disk: Temp space for archive creation (~50-100 MB per job)

### Configuration

- `EASTERN_TZ = ZoneInfo("America/New_York")` - Hardcoded, consider
  parametrization
- `LOGO_PATH = assets/logo.png` - Must exist for header image
- Sheet name limit: 31 characters (Excel standard, enforced in
  package_exporter.py)

---

## Future Enhancement Opportunities

1. **Streaming Exports:** Replace full buffering with streaming for large
   archives
1. **Format Plugins:** Plugin architecture for custom export formats
1. **Async Processing:** Async/celery for long-running exports
1. **Caching:** Cache DataFrames and images to reduce re-computation
1. **Configuration:** Externalize colors, formats, templates
1. **Export Templates:** Custom PDF/PowerPoint templates
1. **Database Exports:** Direct database export (CSV/Parquet)
1. **Real-time Updates:** WebSocket for export progress
1. **Batch Operations:** Export multiple missions in one request
1. **Archive Formats:** Tar.gz, tar.bz2, 7z support
