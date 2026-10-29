# Airfield Weather Toggles Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement inline.

**Goal:** Two independent weather switches: departure and arrival, each showing
both METAR and TAF.

**Architecture:** Persist default-off departure_weather and arrival_weather in
shared aviation settings and display presets. Acquire both station feeds when
either airfield switch is enabled. Filter map reports and picking to the nearest
reporting station within 10 km of the selected route endpoint, using named
departure/arrival waypoints when present. Existing global station switches
continue to show all stations. Reuse controller drawing budgets and lifecycle.

**Tech Stack:** React, TypeScript, Vitest, Python, Pydantic, pytest.

**Spec:** User clarification: “2 switches, one turns on both for arrival, on
turns on both for departure”.

## Global Constraints

- Controls belong in operator weather settings; retain the readable Overview
  map.
- Missing airfield reports mean unknown weather; never use distant stations.
- Preserve existing global weather controls and old saved settings.
- Work in the feature worktree and submit a PR against dev.

## Review Focus

- Each airfield switch independently enables both products.
- Route changes replace endpoint reports and clear old selections.
- Global station toggles continue to work with endpoint switches.
- Legacy settings and presets default the new switches off.
- Disabled and unavailable settings prevent conflicting saves.

## Task 1: Persist airfield visibility and acquire both feeds

- [x] Add failing settings/runtime tests for independent switches, both feed
      acquisition, and disable behavior.
- [x] Add departure_weather and arrival_weather defaults to backend settings,
      frontend schemas, and preset capture/apply.
- [x] Run focused backend and schema tests.

## Task 2: Filter and display airfield weather

- [x] Add failing controller tests for endpoint combinations, global overrides,
      route changes, and missing or distant stations.
- [x] Add route endpoint selection and controller station filtering, preserving
      full cached payloads and drawing ownership.
- [x] Add Departure weather and Arrival weather switches, with METAR and TAF
      explanatory text.
- [x] Run weather unit tests, frontend suite, build and lint; inspect rendered
      controls where available.
- [x] Review, commit, push, and create a PR against dev. Stop and verify all
      owned runtime resources.

## Verification

- Frontend suite: 2,340 tests passed; final endpoint checks: 17 passed.
- Backend weather, settings and preset API checks: 217 passed.
- TypeScript/Vite production build and ESLint passed.
- Production-bundle browser diagnostic passed with intercepted settings APIs:
  independent switches, server-confirmed saves, reload persistence and no page
  errors.
- Independent whole-branch review found no concrete defects.
- Full isolated Docker/browser final acceptance remains a requirement before PR
  approval; the UI diagnostic does not claim that authority.
