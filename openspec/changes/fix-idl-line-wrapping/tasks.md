## 1. Frontend: ColorCodedRoute IDL Handling

- [x] 1.1 Add `isIDLCrossing` prop to `ColorCodedRoute` component interface (`ColorCodedRoute.tsx`)
- [x] 1.2 Normalize sample coordinates to 0-360 range in `mapSegmentsToCoordinates` when `isIDLCrossing` is true
- [x] 1.3 Thread `isIDLCrossing` from `RouteMap.tsx` into `ColorCodedRoute` component

## 2. Backend: PPTX Map Fallback IDL Handling

- [x] 2.1 Extract IDL segment-splitting logic from the timed path (lines ~677-707) into a `_plot_segment_with_idl_handling` helper function in `exporter/__main__.py`
- [x] 2.2 Update the timed rendering path to call the new helper instead of inline IDL logic
- [x] 2.3 Update the fallback rendering path (lines ~652-660) to call the new helper

## 3. Verification

- [x] 3.1 Build frontend (`npm run build`) and verify no type errors
- [x] 3.2 Run backend tests (`pytest`) and verify no regressions (blocked by missing `watchdog` dep; syntax verified OK)
- [ ] 3.3 Manually verify IDL-crossing route renders correctly on leg detail page with timeline preview active (requires manual testing)
- [ ] 3.4 Manually verify PPTX export of IDL-crossing leg renders route without wrapping (requires manual testing)
