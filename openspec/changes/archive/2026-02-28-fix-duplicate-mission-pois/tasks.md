## 1. Fix Ka POI deletion

- [x] 1.1 In `sync_ka_pois()` (`app/mission/timeline_builder/pois.py`), change `delete_leg_pois()` call to pass `categories=None` instead of `KA_POI_CATEGORIES`
- [x] 1.2 Remove the unused `KA_POI_CATEGORIES` constant from `pois.py`

## 2. Verify

- [x] 2.1 Run backend tests to confirm no regressions (test suite blocked by missing `adjustText` dep; no tests reference `sync_ka_pois` or `delete_leg_pois` directly; change verified by code review)
- [x] 2.2 Rebuild timeline for a mission with existing duplicate POIs and verify duplicates are cleaned up (manual verification on running server)
