// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, renderHook } from '@testing-library/react';
import { StrictMode } from 'react';
import {
  useSigmetPresentation,
  type SigmetPresentationInput,
} from './route-sigmet-presentation';
import { routeSnapshot, hash } from '@/test/route-sigmet-fixtures';
import { parseAviationFeatures } from '@/services/aviation-features';
import { routeSigmetSnapshotSchema } from '@/services/route-sigmets';
import { WeatherBudget } from './weather-budget';
import { NOW } from './fixtures';
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
it('releases native drawings and retained source data on route change, hide/offline, disable and unmount in StrictMode', () => {
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
    fillRect() {},
    fillText() {},
  } as unknown as CanvasRenderingContext2D);
  const fixture = routeSnapshot(),
    budget = new WeatherBudget();
  const sourceLease = budget.reserve('source', {
    encoded: 0,
    decoded: 1024,
    gpu: 0,
  });
  const first: SigmetPresentationInput = {
    source: {
      snapshot: routeSigmetSnapshotSchema.parse(fixture.snapshot),
      collection: parseAviationFeatures(fixture.data, 'sigmet'),
      available: true,
      error: null,
      nowMs: NOW,
      dataLease: {
        retain: () =>
          budget.reserve('source', { encoded: 0, decoded: 1024, gpu: 0 }),
      },
    },
    localContextKey: hash('c'),
    intersectingOnly: true,
    nowMs: NOW,
    routePoints: [
      { longitude: -2, latitude: 0 },
      { longitude: 6, latitude: 0 },
    ],
  };
  const hook = renderHook(
    ({ input, enabled }) => useSigmetPresentation(input, enabled, budget),
    { initialProps: { input: first, enabled: true }, wrapper: StrictMode }
  );
  expect(hook.result.current.view.drawing).toBeDefined();
  expect(hook.result.current.highlightUnavailable).toBe(false);
  const allocated = budget.snapshot();
  hook.rerender({
    input: { ...first, localContextKey: hash('9') },
    enabled: true,
  });
  expect(hook.result.current.view.drawing).toBeUndefined();
  expect(budget.snapshot().gpu).toBe(0);
  hook.rerender({ input: first, enabled: true });
  expect(budget.snapshot().gpu).toBe(allocated.gpu);
  hook.rerender({
    input: {
      ...first,
      source: {
        snapshot: null,
        collection: null,
        available: false,
        error: null,
        nowMs: NOW,
        dataLease: null,
      },
    },
    enabled: true,
  });
  expect(hook.result.current.notices).toEqual([]);
  expect(budget.snapshot()).toMatchObject({ gpu: 0, decoded: 1024 });
  hook.rerender({ input: first, enabled: true });
  hook.rerender({ input: first, enabled: false });
  expect(budget.snapshot()).toMatchObject({ gpu: 0, decoded: 1024 });
  hook.rerender({ input: first, enabled: true });
  sourceLease.release();
  expect(budget.snapshot().decoded).toBeGreaterThan(1024);
  hook.unmount();
  expect(budget.snapshot()).toMatchObject({
    encoded: 0,
    decoded: 0,
    gpu: 0,
    slots: 0,
  });
});
