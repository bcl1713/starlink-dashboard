# Overview ADS-B Aircraft Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking. Read this contract and the approved
> spec before the linked task files.

**Goal:** Add globally selected ADS-B aircraft to Overview, with shared saved
Configuration controls, reliable contact expiry, and read-only aircraft details.

**Architecture:** One application-owned asynchronous backend service acquires
adsb.lol traffic and maintains an ephemeral normalized cache. A dedicated atomic
settings store supplies revisioned installation state. Both windows consume the
same filtered bundle; frontend modules own editing, expiry, and globe rendering.

**Tech Stack:** Existing FastAPI, Pydantic, httpx, filelock, pytest; React 19,
TypeScript, React Query, React Three Fiber, Three.js, Radix Dialog, Vitest,
Testing Library, and Playwright Chromium. No new dependency is planned.

**Spec:** [Approved ADS-B addon](../specs/2026-10-03-overview-adsb-aircraft-addon-design.md).

## Global Constraints

- "An optional ADS-B aircraft layer, disabled by default."
- "Two modes: **Military + included** and **Included only**."
- "Exact ICAO hex include and exclude lists, with exclusions always winning."
- "Multiple case-insensitive callsign substrings for background military traffic."
- "Selection is installation-wide and independent of map zoom, camera position,
  the current route, and the own aircraft's location."
- "Require exactly six hexadecimal digits for saved ICAO hex entries, normalize
  their case, preserve leading zeroes, and reject invalid entries with visible
  validation feedback."
- "Poll settings at most five seconds apart while visible, and refresh on
  returning to the foreground."
- "Target a 15-second refresh cycle, coalesce simultaneous browser requests, and
  do not overlap upstream cycles or multiply them by viewer count."
- Position age: "Less than 30 seconds" is current; "At least 30 seconds but less
  than 120 seconds" is stale; "At least 120 seconds" is removed.
- "Age refers to the position observation, not the latest browser poll or HTTP
  success."
- "Every included contact has a persistent callsign label whenever its marker is
  visible." Fallback is registration, then hex; never aggregate these labels.
- "Selection never changes camera framing or replaces the own-aircraft follow
  target. A camera drag must not accidentally select an aircraft."
- "ADS-B data never enters own-aircraft telemetry, route timing, communications
  metrics, or operational warning rules."
- "Persist settings, but do not restore live contact positions from disk after a
  service restart."
- "Verification uses controlled provider fixtures and browser checks rather than
  depending on live traffic availability."
- Preserve route, history, camera intent, telemetry, metrics, links, configured
  satellites, existing warnings, and normal Earth occlusion. No general civilian
  feed, trails, destination inference, alerts, country filters, or ADS-B follow.

## Review Focus

1. HTTP 200 with a malformed envelope or mixed invalid records: report envelope
   failure, isolate bad records, and retain valid contacts only to original expiry
   (Tasks 2–3).
2. A hidden window returning after expiry or a delayed traffic response: expire
   before rendering retained data, refresh on foreground, and never renew a
   position from an old response (Task 4).
3. A settings save racing a military or hex request, including a subsequent
   re-enable: obsolete generations cannot repopulate caches or selection
   (Tasks 3–4).
4. Long identity labels and several included aircraft at nearly identical
   positions: keep individual labels, accessible identity, and offset placement
   without the POI aggregate fallback (Tasks 5–6).
5. Missing track, unknown classification, zero altitude, and `alt_baro: "ground"`:
   retain valid positions, show honest unavailable details and units, and use a
   neutral orientation when track is unavailable (Tasks 2 and 6).

---

## Baseline and authority

Source inspection used clean `feat/starshield-flow-line-arc` at
`d8df56d9209a1b01e2776c4c79a3e919794a35bc` on 2026-10-03. The original request authorized
generating the plan; it did not request product implementation, publishing,
deployment, or contacting the provider. Keep the approved spec unchanged.

Before execution, reconcile the selected implementation base with the traffic
arc/link changes and current `dev`, then use `superpowers:using-git-worktrees`
when isolation is needed. Do not implement against assumed line numbers: the
integration anchors below are named functions/components from this baseline.

### Issue 244 reconciliation on 2026-10-04

The user requested starting issue
[244](https://github.com/bcl1713/starlink-dashboard/issues/244) and an isolated
workspace. Worktree `/tmp/starlink-244`, branch `feat/244-overview-adsb`, starts
from current local `dev` at `913175dc0e19a349a9d724d1e7efcb32f1489099`.
Unrelated uncommitted history-efficiency documents in the original workspace
are excluded. The approved spec, shared wire contracts and seven-task sequence
remain the feature authority. The user approved the reconciled plan and native
execution on 2026-10-04; implementation proceeds in this isolated worktree.

Current integration anchors and decisions:

- `main.py` retains the settings initialization functions, `startup_event`,
  `shutdown_event` and router registration. It now owns an orbital catalog too.
  Add a separate ADS-B store/service/client and cleanup without replacing the
  history or orbital runtimes. The Compose settings mount and single-worker
  Uvicorn command still support the planned persistence/acquisition ownership.
- `OverviewLinkSettings` now includes `orbital_traffic_enabled`. Keep all three
  link fields intact; ADS-B has its own revisioned settings endpoint and does
  not reuse that store or the orbital toggle.
- Overview's existing queries use `overviewRefreshOptions(true)` for background
  polling. ADS-B settings and traffic retain their approved visible-only 5000ms
  polling contract with foreground refresh; do not copy the background override
  or change the existing queries. Preserve the mutation scope and read-cancel
  pattern while adding ADS-B revision guards.
- `ConfigurationPage` now includes orbital diagnostics and display/camera
  controls. Mount the ADS-B card independently of clock loading/error branches,
  preserving every existing card and its query inputs.
- `OverviewPage` now mounts `OrbitalSprites` and chooses an orbital traffic path.
  Add the independent ADS-B scene layer using its existing `globeOccluder`,
  `stageRef` and camera-settled/layout signals. Preserve sprite/link predicates,
  own-aircraft follow and existing legend entries; ADS-B adds its own predicate.
- The shared `DialogContent` portals to `document.body`. Task 6 must supply the
  map stage explicitly to a Radix portal for ADS-B details, leaving that shared
  component's existing consumers intact. Include current POI labels and controls
  in ADS-B label collision reservations without adopting POI aggregation.
- Extend current window fixtures with default-off ADS-B responses and retain the
  complete orbital/link settings payload. Add window-refresh and traffic-path
  browser regressions plus orbital lifecycle/rendering unit checks to acceptance.

Preparation evidence: the existing link query/mutation, Overview refresh,
Configuration and legend test files passed in the isolated worktree (5 files,
61 tests). They used the existing frontend dependency installation through an
local package symlinks under ignored `node_modules`; no versions changed.
The actor's configured Docker daemon was verified without changing its endpoint/context:
`unix:///run/user/1002/docker.sock`, context `default`, Docker `29.8.1`,
storage driver `overlayfs`. No ADS-B product checks, image builds or production
acceptance have run; the feature remains unimplemented.

The existing Dockerfile runs one Uvicorn worker. This plan preserves that runtime
and owns one acquisition service there; adding workers/replicas requires separate
coordination work. Do not create an acquisition singleton per API request.

## Shared contracts and file ownership

All wire names use snake_case. All timestamps below are epoch milliseconds.
Python types live in `app/models/overview_adsb.py`; matching TypeScript types and
runtime parsers live in `src/services/overview-adsb.ts`.

| Contract             | Exact fields                                                                                                                                                                                                                                                                                                                      |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `AdsbSettings`       | `enabled: bool = false`, `mode: "military_and_included" \| "included_only" = "military_and_included"`, `include_hexes: list[str] = []`, `exclude_hexes: list[str] = []`, `callsign_substrings: list[str] = []`, `revision: int = 0`                                                                                               |
| `AdsbSettingsUpdate` | Nonempty partial of the five editable fields; strict types; no null, unknown field, or client-supplied revision                                                                                                                                                                                                                   |
| `AdsbAltitude`       | `value: float`, `unit: "ft"`, `source: "barometric" \| "geometric"`                                                                                                                                                                                                                                                               |
| `AdsbContact`        | `hex: str`, `callsign: str \| null`, `registration: str \| null`, `aircraft_type: str \| null`, `military: bool \| null`, `latitude: float`, `longitude: float`, `altitude: AdsbAltitude \| null`, `ground_speed_knots: float \| null`, `track_degrees: float \| null`, `position_observed_at_ms: float`, `acquired_at_ms: float` |
| `AdsbSourceStatus`   | `key: "military" \| "hex:<normalized-hex>"`, `last_success_at_ms: float \| null`, `error: str \| null`, `retry_at_ms: float \| null`                                                                                                                                                                                              |
| `AdsbTrafficBundle`  | `settings_revision: int`, `generated_at_ms: float`, `contacts: list[AdsbContact]`, `sources: list[AdsbSourceStatus]`                                                                                                                                                                                                              |

Normalize hexes and callsign substrings to uppercase, trim strings, and deduplicate
in first-entry order. Preserve overlap between include and exclude lists.
Military classification is tri-state: provider military endpoint provenance is
true; explicit lookups use documented `dbFlags & 1`; missing flags are unknown.
Callsigns cannot establish classification. Rendered inclusion is derived from
confirmed settings rather than stored on contacts.

Endpoints: `GET /api/overview-adsb/settings`,
`PUT /api/overview-adsb/settings`, and `GET /api/overview-adsb/traffic`.
Settings endpoints return complete `AdsbSettings`; traffic returns the current
filtered `AdsbTrafficBundle` without waiting for upstream acquisition. Invalid
updates return 422; unavailable/corrupt settings return 503 without replacement.
Source failures are represented in a successful traffic bundle independently.

Store settings at `data/settings/overview-adsb.json` using the existing persistent
data volume. FileLock, read/merge/write, fsync and atomic replace follow
`app/services/overview_link_settings.py`; a successful nonempty update increments
revision under the same lock. No positions or source cache are written to disk.

## Task sequence

1. [Backend tasks 1–3](2026-10-03-overview-adsb-aircraft-layer-backend.md): settings
   persistence/API; provider normalization and selection; acquisition/cache/API
   with application lifecycle.
2. [Frontend tasks 4–6](2026-10-03-overview-adsb-aircraft-layer-frontend.md): shared
   query/revision/freshness state; Configuration controls/table; globe markers,
   labels/details and integration.
3. [Acceptance task 7](2026-10-03-overview-adsb-aircraft-layer-acceptance.md):
   cross-window browser tests, performance evidence, real production path, and
   documentation.

Each task file declares exact files, interfaces, failing tests, implementation,
passing checks and a task commit. Tasks 2 and 5 have isolated responsibilities,
but native sequential execution is recommended: the seven tasks share revision,
freshness and globe contracts, so retaining context should reduce interface drift.

## Provider references and rollout boundary

Checked the [published adsb.lol schema](https://api.adsb.lol/api/openapi.json)
on 2026-10-03: `/v2/mil`, `/v2/hex/{icao_hex}`, response `ac`/`now`, nullable
`dbFlags`, and `lastPosition` with its own `seen_pos` are present. Use single-hex
requests only. The [readsb reference](https://github.com/wiedehopf/readsb/blob/dev/README-json.md)
defines v2 `now` in milliseconds, `seen_pos` in seconds, altitude in feet, ground
speed in knots, true track, and the military flag. Keep these unit conversions
in the adapter rather than frontend views.

Configuration attribution links to [adsb.lol](https://www.adsb.lol/) and the
[ODbL license](https://opendatacommons.org/licenses/odbl/1-0/). Recheck the
[provider API documentation](https://api.adsb.lol/docs) usage requirements before
production rollout. No maintainer contact or live-traffic dependency is needed
to implement and accept controlled-fixture behavior.

## Plan self-review and handoff

Coverage: acceptance criteria 1–4 map to Tasks 1–4; 5 to Tasks 4–5; 6 to Task 6;
7 to Tasks 1, 3–5 and 7; 8 to Tasks 2–4 and 7; 9 to Tasks 3–4, 6–7; 10 to
Tasks 6–7. The five Review Focus cases have named tests in their owning tasks.
No deferred orbital work or worldwide civilian collection is introduced.

The user approved the reconciled plan and selected native execution on
2026-10-04. Use `superpowers:executing-plans` with a final independent review.
Merge, deployment and provider contact remain outside the authorized work.
