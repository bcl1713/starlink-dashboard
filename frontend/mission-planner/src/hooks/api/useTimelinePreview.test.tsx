/** @vitest-environment jsdom */
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import {
  timelineService,
  type Timeline,
  type TimelinePreviewRequest,
} from '@/services/timeline';
import { popForecast } from '@/test/pop-fixtures';
import { useTimelinePreview } from './useTimelinePreview';
vi.mock('@/services/timeline', () => ({
  timelineService: { previewTimeline: vi.fn() },
}));
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.clearAllMocks();
});
const request = { transports: {} } as TimelinePreviewRequest;
const timeline = (revision: string): Timeline => ({
  mission_leg_id: 'one',
  created_at: '2035-01-01',
  segments: [],
  pop_forecast: popForecast(revision),
});
it('rejects late route revisions even when the old HTTP operation ignores cancellation', async () => {
  vi.useFakeTimers();
  let resolveOld!: (value: Timeline) => void,
    resolveNew!: (value: Timeline) => void;
  vi.mocked(timelineService.previewTimeline)
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveOld = resolve;
        })
    )
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveNew = resolve;
        })
    );
  const { result, rerender } = renderHook(
    ({ req }) => useTimelinePreview('mission', 'one', req, { debounceMs: 1 }),
    { initialProps: { req: request } }
  );
  await act(async () => {
    vi.advanceTimersByTime(1);
  });
  rerender({
    req: { ...request, adjusted_departure_time: '2035-03-02T00:00:00Z' },
  });
  await act(async () => {
    vi.advanceTimersByTime(1);
    resolveNew(timeline('new-route'));
  });
  expect(result.current.preview?.pop_forecast?.revision).toBe('new-route');
  await act(async () => {
    resolveOld(timeline('old-route'));
  });
  expect(result.current.preview?.pop_forecast?.revision).toBe('new-route');
});
it('clears old evidence immediately during route changes and disabled/absent input', async () => {
  vi.useFakeTimers();
  vi.mocked(timelineService.previewTimeline).mockResolvedValue(
    timeline('old-route')
  );
  const { result, rerender } = renderHook(
    ({
      leg,
      req,
      enabled,
    }: {
      leg: string;
      req: TimelinePreviewRequest | null;
      enabled: boolean;
    }) => useTimelinePreview('mission', leg, req, { enabled, debounceMs: 1 }),
    {
      initialProps: {
        leg: 'one',
        req: request as TimelinePreviewRequest | null,
        enabled: true,
      },
    }
  );
  await act(async () => {
    vi.advanceTimersByTime(1);
  });
  expect(result.current.preview).not.toBeNull();
  rerender({ leg: 'two', req: request, enabled: true });
  expect(result.current.preview).toBeNull();
  rerender({ leg: 'two', req: null, enabled: false });
  expect(result.current.isCalculating).toBe(false);
});
