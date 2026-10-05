# ADS-B Layer Frontend Tasks

Read the [main plan and shared contracts](2026-10-03-overview-adsb-aircraft-layer.md)
and approved spec first. Paths here are relative to
`frontend/mission-planner/`; run npm commands from that directory.

## Task 4: Shared queries, revision guards and local freshness

**Files:** Create `src/services/overview-adsb.ts` and `.test.ts`;
`src/hooks/api/useOverviewAdsbSettings.ts`,
`useUpdateOverviewAdsbSettings.ts`, `useOverviewAdsbTraffic.ts`, and matching
`.test.ts` files; `src/hooks/useOverviewAdsbLayer.ts` and `.test.tsx`;
`src/pages/adsb/overview-adsb-state.ts` and `.test.ts`.

**Interfaces:** TypeScript wire types match the main plan exactly, using
`boolean`, `number`, arrays and nullable fields. `overviewAdsbApi` exposes
`getSettings(signal?: AbortSignal): Promise<AdsbSettings>`,
`updateSettings(changes: AdsbSettingsUpdate): Promise<AdsbSettings>`, and
`getTraffic(signal?: AbortSignal): Promise<AdsbTrafficBundle>`.
Query keys are `['overview-adsb-settings']` and `['overview-adsb-traffic']`.
`useOverviewAdsbSettings()` and `useUpdateOverviewAdsbSettings()` return
React Query results; `useOverviewAdsbTraffic(enabled: boolean)` gates reads.

State export:
`projectAdsbContacts(contacts: readonly AdsbContact[], settings: AdsbSettings,
nowMs: number): AdsbContactView[]`. `AdsbContactView` extends the contact with
`included: boolean`, `freshness: 'current' | 'stale'`,
`position_age_seconds: number`, and `label: string`.
`useOverviewAdsbLayer()` returns
`{ settings: AdsbSettings | undefined, contacts: AdsbContactView[],
sources: AdsbSourceStatus[], settingsError: boolean, trafficError: boolean }`.
Both pages use this hook; it owns one enabled-only 1s freshness timer per mount.

- [x] **Step 1: Write failing service, hook and state tests.** API tests assert
  exact URLs, abort propagation, full confirmed PUT response, and rejection of
  malformed revisions/types/positions/timestamps. Do not coerce provider data.
  `test_settings_poll_every_five_seconds_and_on_focus` asserts visible polling
  at 5000ms, background polling off, focus refresh and `retry: false`.
  `test_save_failure_keeps_confirmed_state` rejects PUT and asserts no optimistic
  list, switch, revision or traffic replacement.
  `test_late_settings_get_keeps_newer_put` resolves an older GET after save;
  revision 2 remains current.
  `test_old_traffic_cannot_resurrect_exclusion` resolves revision 1 traffic after
  revision 2 excludes its hex: no marker/table row. Higher traffic revision waits
  for confirmed settings, triggers settings refresh, and is never projected
  against older filters. Test a queued second save and read during PUT too.
  `test_new_settings_reproject_retained_contacts` confirms include labeling,
  removal of inclusion, exclusion and mode change before another traffic reply.
  `test_initial_settings_failure_is_off` proves no traffic requests without a
  confirmed enabled configuration; cached confirmed settings survive refetch
  failure with Configuration error feedback. Disabled clears contacts/sources.
  `test_freshness_advances_while_requests_fail` asserts 29.999/30/119.999/120s
  boundaries, deduplication, and retained contacts expiring despite errors.
  `test_foreground_expires_before_repaint` returns after a hidden 130s interval
  and expects no old contact plus immediate settings/traffic refresh.
  `test_delayed_or_repeated_response_never_renews_position` receives the same
  observation timestamp after 130s of delay: no contact is rendered on arrival.
  Repeated responses and browser polls never replace observation time with receipt.
  `test_disable_unmount_cleans_polling_and_timer` checks aborts and timer cleanup.
  With a military contact observed at `1791028800000`, empty callsign filters,
  and confirmed enabled military-mode settings:

  ```ts
  expect(projectAdsbContacts([contact], settings, 1791028830000)[0].freshness)
    .toBe('stale');
  expect(projectAdsbContacts([contact], settings, 1791028920000)).toEqual([]);
  ```

- [x] **Step 2: Verify failure.** Run the new service, hook and state test files
  with `npm run test:unit -- <files>`; expect missing modules/exports.
- [x] **Step 3: Implement API validation and revision-safe query hooks.** Reuse
  the existing axios api-client and confirmed-settings patterns. Poll settings
  and enabled traffic at 5000ms, refresh both on window focus and visible
  `visibilitychange`; neither polls in background. Do not apply
  `overviewRefreshOptions(true)`: current Overview queries use that override to
  poll in background, unlike the ADS-B contract. Preserve those existing query
  policies. Serialize ADS-B saves with mutation
  scope `overview-adsb-settings`, cancel GETs before/after PUT, and publish only
  complete confirmed settings. Keep the highest confirmed settings revision
  when a delayed GET completes; never let structural sharing accept an older one.
  Invalidate traffic after confirmed save; no browser-local invalidation can
  replace the other window's independent settings polling.
- [x] **Step 4: Implement projection and layer hook.** Match Task 4 signatures.
  Keep the last accepted contact snapshot through traffic errors/revision gaps
  and reapply the complete current filter precedence locally on every settings
  confirmation. Only accept a newly arriving bundle when its revision matches
  current confirmed settings; ignore older bundles, hold newer ones until a
  settings refresh confirms them. Also reject regressing `generated_at_ms` and
  older per-hex observation times. Disable clears the retained snapshot and
  associated state so re-enable cannot reuse contacts from an earlier generation.
  Compute age from epoch `Date.now()` minus `position_observed_at_ms`, preserving
  observation timestamps through receipt, polling and errors. Tick freshness
  without upstream requests; never anchor age to bundle generation or arrival.
  Recompute synchronously on foreground and contact receipt before projection.
  Derive inclusion and identity fallbacks from confirmed state; never write these
  queries into mission, telemetry, history or camera stores.
- [x] **Step 5: Verify success.** Rerun all Task 4 files plus existing link-settings
  service/query/mutation tests; expect PASS. Inspect race and cleanup assertions.
- [x] **Step 6: Commit Task 4 files.**
  `git commit -m "feat(adsb): synchronize confirmed settings and contact freshness"`.

## Task 5: Configuration editing and active contact table

**Files:** Create `src/pages/adsb/OverviewAdsbSettingsCard.tsx`,
`OverviewAdsbContactTable.tsx`, `OverviewAdsbLists.tsx`, and their `.test.tsx`
files. Modify `src/pages/ConfigurationPage.tsx` imports/card mounting and
`ConfigurationPage.test.tsx`.

**Interfaces:** `OverviewAdsbSettingsCard()` owns Task 4's layer/update hooks.
`OverviewAdsbContactTable({ contacts, disabled, onInclude, onExclude })` takes
`contacts: readonly AdsbContactView[]`, `disabled: boolean`, and callbacks
`(hex: string) => void`. `OverviewAdsbLists({ settings, disabled, onSave })`
takes `AdsbSettings`, `boolean`, and `(changes: AdsbSettingsUpdate) => void`.
Both child views are presentation-only; the parent owns saved-state feedback.

- [x] **Step 1: Write failing component/integration tests.** Assert default off,
  exact mode names, controlled enable/mode edits, and preserved other fields.
  Test separate include/exclude editors, newline or comma-separated exact hexes,
  visible invalid-entry feedback, normalization, and leading-zero preservation.
  Callsign editor uses comma/newline entries, trims and deduplicates with OR copy.
  `test_table_is_active_global_layer_not_viewport_discovery` supplies contacts
  behind the globe/outside the camera and expects all rows; disabled produces no
  active rows while saved lists remain editable. Include saves stable hex despite
  a subsequent callsign change; Exclude removes row after confirmation, not before.
  Removing inclusion leaves an eligible military row without inclusion status;
  removing exclusion restores eligibility once acquisition supplies it again.
  `test_unavailable_and_conflicting_saved_entries_remain_editable` expects absent
  included entries and both lists' overlap to remain, with explicit explanation
  that exclusion wins and separate Remove actions. Never silently resolve it.
  `test_long_and_missing_identities` expects callsign, then registration, then
  hex, wrapping a long identity rather than hiding row actions.
  Pending saves disable edits; loading/GET error/PUT error/success have distinct
  accessible feedback and failed saves retain confirmed values. Source errors
  and per-source last-success times are displayed without a global map warning.
  Assert provider attribution/license links and every existing Configuration
  card remains available when ADS-B settings fail, including orbital diagnostics,
  link settings, display controls and operational clocks.
  After a confirmed exclusion of the fixture row `00AB12`, assert:

  ```ts
  expect(screen.queryByRole('row', { name: /00AB12/ })).not.toBeInTheDocument();
  expect(screen.getByRole('region', { name: /saved excluded aircraft/i }))
    .toHaveTextContent('00AB12');
  ```

- [x] **Step 2: Verify failure.** Run the three new component files and
  `src/pages/ConfigurationPage.test.tsx`; expect missing components/section.
- [x] **Step 3: Implement the views and mount the card.** Follow existing
  `OverviewLinkSettingsCard` form/save conventions. Table columns: hex, identity,
  included/background status, Current/Stale age, Include and Exclude actions;
  stable hex row keys and deterministic hex sorting. Replace the relevant saved
  list with its normalized union when including/excluding; disable while pending.
  Editors submit only changed fields; synchronize confirmed values without
  wiping unrelated unsaved text during a poll. Show empty/disabled table states.
  Saved-list Remove actions affect only their own list. Label the editor regions
  `Saved included aircraft` and `Saved excluded aircraft`. Include attribution
  `Aircraft data: adsb.lol` and `ODbL license` using main-plan links.
  Mount independently of operational-clock loading/error branches.
- [x] **Step 4: Verify success.** Rerun Task 5 and Configuration tests; expect PASS.
- [x] **Step 5: Commit Task 5 files.**
  `git commit -m "feat(configuration): edit ADS-B lists and selected traffic"`.

## Task 6: Batched globe markers, persistent labels and read-only details

**Files:** Create under `src/pages/adsb/`: `OverviewAdsbLayer.tsx`,
`overview-adsb-marker-rendering.ts`, `overview-adsb-label-layout.ts`,
`OverviewAdsbDetails.tsx`, `OverviewAdsb.css`, and corresponding `.test.ts(x)`
files. Modify `src/pages/OverviewPage.tsx` layer hook/selection/scene mount,
`OverviewMapLegend.tsx` props/entries, `OverviewPage.layers.test.tsx`,
`OverviewMapLegend.test.tsx`, and `OverviewPage.css` ADS-B legend sample.

**Interfaces:** `buildAdsbMarkerInstances(contacts: readonly AdsbContactView[]):
AdsbMarkerInstances` defines typed arrays for hex-indexed instance matrices
and current/stale styling, with no contact truncation. Export that return type.
`layoutAdsbLabels(labels: readonly ProjectedPoiLabel[],
viewport: { width: number; height: number }, reserved: readonly Bounds[]):
Record<string, readonly [number, number]>` defines/exports its own `Bounds`
shape `{x,y,width,height}`; reuse the POI projected-label type only.
`OverviewAdsbLayer({ contacts, globeOccluder, onSelect, onVisibleHexesChange })`
takes readonly views, `RefObject<THREE.Group>`, `(hex: string) => void`, and
`(hexes: readonly string[]) => void` respectively.
`OverviewAdsbDetails({ contact, onClose, returnFocusRef, portalContainer })` takes
`AdsbContactView | null`, `() => void`, and `RefObject<HTMLElement | null>`.
Its `portalContainer: HTMLElement | null` is supplied from Overview's map stage.
Add `adsb?: boolean` default false to `OverviewMapLegend`.

- [ ] **Step 1: Write failing rendering/interaction tests.** Assert legal globe
  projection/clearance, tangent orientation from track 0/90/180/270, neutral missing
  track, one instance per hex, and unchanged buffers between dataset updates.
  No altitude measurement is invented by surface placement. Both depth testing
  and rear-globe selection rejection are required. Included-only Html labels
  use callsign/registration/hex fallback with Earth occlusion; background has no
  permanent DOM labels. Stale style includes a shape/symbol and text, not color
  alone, and keeps included labels. Label-layout tests include long text,
  coincident points and reserved overlays: return every hex offset, never a count.
  Details tests assert all contract fields, `ft` plus altitude source, knots,
  an explicit map-stage portal container (including native fullscreen),
  `Track` rather than heading, position age and Current/Stale, explicit
  `Unavailable`, Close, Escape, dialog focus and focus restoration; no editing.
  Page tests assert click selects a contact but never camera/follow state; drag
  greater than 5 CSS pixels does not select. Selection follows current contact
  details and closes on expiry, exclusion, or disable. ADS-B legend appears only
  with active contacts; camera occlusion alone does not toggle it.
  Disable/unmount tests assert geometry/material/buffer disposal, label removal,
  cleared selection and released event/measurement work. Existing telemetry,
  route/history, links, metrics and warnings retain the same inputs/guards.
  For selected contact details, assert exact terminology and absent editing:

  ```ts
  expect(screen.getByRole('dialog')).toHaveTextContent('Track');
  expect(screen.queryByRole('button', { name: 'Include' })).toBeNull();
  expect(screen.queryByRole('button', { name: 'Exclude' })).toBeNull();
  ```

- [ ] **Step 2: Verify failure.** Run new rendering/layout/details tests and the
  changed page/legend tests; expect missing exports/behavior.
- [ ] **Step 3: Implement batched aircraft rendering and label layout.** Use one
  instanced aircraft-glyph mesh per visual treatment; subdued size/color relative
  to own aircraft. Project with `globePosition` and `ROUTE_OVERLAY_RADIUS`, using
  observed track in the local tangent basis. No interpolation or extrapolation.
  Enable normal depth occlusion and test visibility before accepting raycast
  selection. Rebuild matrices only when contacts change; frame work must not
  re-filter/re-project the dataset. Use Html only for included labels, occluding
  against the existing globe ref; keep stale symbols on all stale glyphs.
  Measure/reposition included labels after contact/camera/layout changes, not
  every animation frame. Publish visible hexes after contact or camera changes
  for the keyboard list; this is presentation visibility, never traffic filtering.
  Share POI packing ideas but never its aggregate/hide
  fallback: choose the least-overlapping offset if a collision-free one is
  impossible, keeping every included identity present. Avoid existing overlays.
  Reserve visible POI label bounds too; do not modify their aggregation policy.
- [ ] **Step 4: Implement details and Overview integration.** Match Task 6 props.
  Use Radix Dialog for focus/Escape with an explicit
  `<DialogPortal container={portalContainer}>` and Radix Content inside it so
  native fullscreen retains it. The shared `components/ui/dialog.tsx`
  `DialogContent` always portals to the body; use the primitives directly for
  this view without changing existing dialogs. Restore focus to the previously
  focused map control or the stage if the marker has no DOM focus target. Make
  the stage programmatically focusable for that fallback. Store selected hex,
  derive the live selected contact and clear when absent. Track pointer-down/up
  displacement before invoking onSelect; no camera callbacks or own follow target
  mutation. Provide an accessible contact list of detail-opening buttons for
  keyboard access without permanent background map labels; button names are
  `Details for <hex>`. Match visible marker
  eligibility. Integrate only the hook, scene component, details and legend
  predicate in Overview; provider/list-editing logic stays in its modules.
- [ ] **Step 5: Verify success.** Run Task 6 tests plus existing page, camera,
  fullscreen, globe coordinate, POI marker/label and flow-consumer unit tests;
  also run `useOrbitalTraffic.test.ts`, `OrbitalTrafficDiagnostics.test.tsx`,
  `orbital/OrbitalSprites.test.tsx` and `orbital/lifecycle.test.ts` against the
  current orbital/link integration. Expect PASS. Rendered
  geometry/occlusion/performance proof remains Task 7.
- [ ] **Step 6: Commit Task 6 files.**
  `git commit -m "feat(overview): render ADS-B contacts labels and aircraft details"`.
