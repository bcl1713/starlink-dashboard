## 1. Fix TypeScript Type

- [x] 1.1 Update `TimelinePreviewRequest` in `src/services/timeline.ts` — replace `to_satellite: string` with `id: string` and `target_satellite_id: string` in the x_transitions array item type

## 2. Fix Preview Request Mapping

- [x] 2.1 Update the x_transitions mapping in `src/pages/LegDetailPage.tsx` `previewRequest` useMemo to pass through `id` and `target_satellite_id` instead of renaming to `to_satellite`

## 3. Verify

- [x] 3.1 Build the frontend (`npm run build`) and confirm no type errors
- [x] 3.2 Manually test: add an X-Band satellite transition and verify timeline preview succeeds without 500 error
