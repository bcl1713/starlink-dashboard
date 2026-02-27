## Why

The timeline preview fails with a 500 error when X-Band satellite transitions are configured. The frontend's `TimelinePreviewRequest` type uses `to_satellite` instead of `target_satellite_id` and omits the `id` field, causing Pydantic validation failures on the backend's `TransportConfig.x_transitions` model.

## What Changes

- Fix the `TimelinePreviewRequest` TypeScript type in `services/timeline.ts` to include `id` and `target_satellite_id` fields (replacing `to_satellite`)
- Fix the preview request mapping in `LegDetailPage.tsx` to pass through `id` and `target_satellite_id` instead of renaming to `to_satellite`

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `timeline-preview`: The preview request payload for x_transitions must include `id` and `target_satellite_id` fields to match the backend's `XTransition` Pydantic model contract.

## Impact

- **Frontend**: `src/services/timeline.ts` (type definition), `src/pages/LegDetailPage.tsx` (request mapping)
- **Backend**: No changes needed — the backend model is correct
- **User-facing**: X-Band satellite transitions will produce valid timeline previews instead of 500 errors
