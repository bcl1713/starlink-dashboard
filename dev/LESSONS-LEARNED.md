# Lessons Learned (Project-Wide)

> This file accumulates lessons learned from ALL features and fixes. Each entry
> is append-only and dated. It is okay for this file to be empty when first
> created.

---

## Entries

<!--
Add entries in this format:

- [YYYY-MM-DD] Short lesson description (optional link to PR/commit/path)
-->

- [2025-11-15] Curl multiline JSON payloads: Inline JSON with unescaped newlines causes "blank argument" errors. Solution: Use `cat > /tmp/file.json << 'EOF'` with heredoc syntax, then reference with `-d @/tmp/file.json`. This is more readable and maintainable than trying to escape special characters in inline JSON. (feature/mission-comm-planning: d8902f1)
- [2025-11-16] Docker layer caching bypasses code changes: Always use `docker compose down && docker compose build --no-cache && docker compose up -d` when Python code changes. Simply running `docker compose up` or `docker compose restart` will serve cached code from previous builds, making changes appear ineffective. This is critical for test execution and verification. (feature/mission-comm-planning: d8fd695)
- [2025-11-16] Time management in Docker rebuilds: Docker rebuilds take 60–90 seconds. Using `sleep 30+` wastes time waiting. Optimal: `sleep 5` then check `docker compose ps` for healthy status. This saves ~25 seconds per rebuild cycle during iterative testing. (feature/mission-comm-planning: 3fe0c84)
- [2025-11-16] Benchmark script dependencies: Performance benchmarking scripts must pre-create or load test data (routes, missions) before timeline computations. RouteManager uses in-memory `_routes` dict; test routes must exist before build_mission_timeline() is called. Solution: Initialize managers, then `route_manager._routes[route_id] = Route(...)` to inject test data. (feature/mission-comm-planning: Session 9)
- [2025-11-17] ParsedRoute object structure: `ParsedRoute` objects from `RouteManager.get_active_route()` do not have a direct `.id` attribute. Route IDs must be extracted from `route.metadata.file_path` using `Path(file_path).stem`. Attempting to access `route.id` will cause AttributeError. This was discovered when implementing active status calculation for route-associated POIs. Solution: `active_route_id = Path(active_route.metadata.file_path).stem` (feat/poi-active-field)
- [2025-11-17] Mission model design pattern: Mission models store `route_id` (string ID), NOT a `route` object. This is by design for loose coupling. When you need route data, you must fetch it from RouteManager using `route_manager.get_route(mission.route_id)`. Similarly, never assume related objects are populated; fetch them from their respective managers. This pattern applies across routes, POIs, and other related entities. Discovered when implementing map generation for exports—code tried `mission.route` which doesn't exist. Solution: Pass RouteManager instance to exporter, use global variable with setter function pattern (main.py calls `exporter.set_route_manager()`), then `route = _route_manager.get_route(mission.route_id)`. (feat/excel-sheet1-timeline-summary: 7158620)
