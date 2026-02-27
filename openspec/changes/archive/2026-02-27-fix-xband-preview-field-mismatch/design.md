## Context

The frontend constructs a `TimelinePreviewRequest` to POST to the backend's timeline preview endpoint. The backend deserializes this into a `TransportConfig` Pydantic model, which expects `x_transitions` items to conform to the `XTransition` model (`id`, `latitude`, `longitude`, `target_satellite_id`, etc.).

Currently, the frontend's preview request mapping in `LegDetailPage.tsx` renames `target_satellite_id` to `to_satellite` and drops `id` entirely. The `TimelinePreviewRequest` type in `services/timeline.ts` codifies this wrong shape.

The `XBandConfig` component and the save handler both use the correct field names — only the preview request path is broken.

## Goals / Non-Goals

**Goals:**
- Fix the preview request to send `id` and `target_satellite_id` as the backend expects
- Align the `TimelinePreviewRequest` TypeScript type with the backend's `XTransition` model

**Non-Goals:**
- Changing the backend model
- Adding new fields or capabilities to x_transitions
- Refactoring the preview request construction beyond the field fix

## Decisions

**Pass x_transition fields through directly instead of remapping.**

The `XBandTransition` frontend type already has the correct field names (`id`, `target_satellite_id`). The mapping in `LegDetailPage.tsx` destructures and renames them unnecessarily. The fix is to pass the fields through as-is, matching what the save handler already does.

Alternative considered: Adding backend aliases (e.g., `to_satellite` as a Pydantic alias) — rejected because the frontend type is already correct and the rename was clearly unintentional.

## Risks / Trade-offs

Minimal risk — this is a bug fix aligning two fields that are already correct on both sides independently. The save path already works with the correct field names, confirming the backend contract.
