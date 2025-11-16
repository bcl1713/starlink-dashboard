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
