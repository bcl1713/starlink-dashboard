# Overview cross-window initial investigation

**Date:** 2026-10-04

**Issue:** [257](https://github.com/bcl1713/starlink-dashboard/issues/257)

**Status:** Initial diagnosis complete; Tasks 1–4 are delivered and the real
production workflow has passed Task 5 journeys. Integrated acceptance remains
incomplete because required browser regressions fail. See the
[acceptance report](2026-10-04-overview-window-sync-acceptance.md).

## Isolation and base

Created `feat/257-overview-window-sync` at `/tmp/starlink-257` from `origin/dev`
commit `f71a7034955bbbd8805d3310ae92af4e86581383`, independently of the existing
PR 258 checkout. GitHub subsequently reported PR 258 merged at 2026-10-04
10:42:35 UTC. Rebasing onto its merge `c8a69d25ba1e58140424d87c644d8aacb62c9d54`
succeeded without conflicts.

## Static findings

Overview's clocks, history-settings, routes/list-detail, and satellite queries
have no periodic refresh. Link-settings polling does not run in the background.
Mission activation/deactivation invalidates the editing window's clock query;
that query client is independent of another window's client. Upcoming mission
POIs, status, and active X-band link already poll in the background.
Camera-follow preferences already use local-storage events.

These are inspected code paths, not proof that every reported mission scenario
has been reproduced. Mission route changes, active-leg edits, Configuration GPS
changes, and history/link propagation need coverage during implementation.

## Two-page clock reproduction

Used the unchanged production frontend build on loopback port 5277 with Chromium
153.0.8010.12, Playwright's headless shell, and SwiftShader. Two pages shared
one browser context, with the Configuration page brought to the front.
Context-level API interception maintained one shared fixture-backed clock store.

1. Loaded Overview and observed the Omaha clock.
2. Opened Configuration in the second page.
3. Changed clock 3's label to `Issue 257 updated clock` and timezone to
   `Pacific/Honolulu`; clicked the real form's save control.
4. Observed the successful PUT, then left Configuration in front for 6.5
   seconds.
5. Overview retained the old clock label. Its clock endpoint had only one GET.
   Configuration had two GETs and one PUT.
6. Reloaded Overview: it fetched and displayed the updated clock label.

This establishes the missed refresh boundary with a successful controlled save.
It does not constitute acceptance through a real backend, separately managed
native OS windows, or native fullscreen.

## Fullscreen feasibility probe

A separate minimal same-origin page opened a popup from a trusted button click.
Another trusted controller click called the popup document's requestFullscreen.
The request rejected with `TypeError: Permissions check failed`. Clicking a
local button inside the popup succeeded and set its document.fullscreenElement.

The [Fullscreen API standard](https://fullscreen.spec.whatwg.org/) requires
transient user activation in the relevant window. The observed outcome supports
an explicit local-click fallback when the browser rejects a remote request. It
does not establish universal failure across browsers or specially granted
browser policies. No activation-bypassing launch options were used.

## Frontend baseline

Ran `./tools/verify frontend` in the original checkout using its installed
dependencies. Git object IDs confirmed that its frontend tree and the worktree's
dev frontend were identical: `95a83b072afad98f9a080103f986e1bbc1dcede0`. PR 258
only changes backend code/tests and its investigation documentation, so the
rebase does not change this frontend tree.

Result: 82 unit-test files / 619 tests passed; TypeScript/Vite production build
passed. Node was v22.12.0 and npm 10.9.0. The existing large-chunk advisory
remains; these checks do not certify browser performance or cross-window
acceptance.

Local diagnostic artifacts:

- `/tmp/starlink-257-frontend-baseline.log`: canonical frontend baseline output.
- `/tmp/starlink-257-browser-audit.cjs`: throwaway diagnostic runner.
- `/tmp/starlink-257-browser-audit.json`: browser result and request counts.

The diagnostic browser was closed and the loopback preview stopped afterward. No
product code was changed. The accompanying design is a draft for user review.
