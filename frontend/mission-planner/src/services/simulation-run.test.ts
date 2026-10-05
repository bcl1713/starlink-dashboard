import { beforeEach, expect, it, vi } from 'vitest';
import {
  simulationRunApi,
  simulationRunSchema,
  pacingSchema,
} from './simulation-run';
import {
  preview,
  runningStatus,
  completedStatus,
} from '@/test/simulation-run-fixtures';
import { apiClient } from './api-client';
vi.mock('./api-client', () => ({ apiClient: { get: vi.fn(), post: vi.fn() } }));
beforeEach(() => vi.resetAllMocks());
it('validates confirmed running and terminal contracts', () => {
  const run = runningStatus().run!;
  expect(simulationRunSchema.parse({ ...runningStatus(), run }).state).toBe(
    'running'
  );
  const terminal = completedStatus().run!;
  expect(
    simulationRunSchema.parse({ ...completedStatus(), run: terminal }).state
  ).toBe('completed');
});
it.each([
  { state: 'idle' },
  { run: null },
  { revision: -1 },
  { served_at: 'bad' },
  { unexpected: true },
  { run: { ...runningStatus().run!, progress_percent: 101 } },
  { run: { ...runningStatus().run!, phase: 'post_arrival' } },
  { run: { ...runningStatus().run!, effective_multiplier: Infinity } },
  { run: { ...runningStatus().run!, effective_multiplier: 0.01 } },
])('rejects malformed status %j', (patch) => {
  expect(
    simulationRunSchema.safeParse({ ...runningStatus(), ...patch }).success
  ).toBe(false);
});
it.each([0.1, 1, 1000])('accepts multiplier boundary %s', (multiplier) => {
  expect(pacingSchema.parse({ mode: 'multiplier', multiplier })).toEqual({
    mode: 'multiplier',
    multiplier,
  });
});
it.each([0, 0.09, 1001, NaN, Infinity, '10'])(
  'rejects multiplier %s',
  (multiplier) => {
    expect(
      pacingSchema.safeParse({ mode: 'multiplier', multiplier }).success
    ).toBe(false);
  }
);
it('previews only one selected pacing mode and forwards cancellation', async () => {
  vi.mocked(apiClient.post).mockResolvedValue({ data: preview });
  const signal = new AbortController().signal;
  await simulationRunApi.preview(
    'mission-1',
    'leg-1',
    { mode: 'target_runtime', runtime_seconds: 120 },
    signal
  );
  expect(apiClient.post).toHaveBeenCalledWith(
    '/api/v2/missions/mission-1/legs/leg-1/simulation/preview',
    { mode: 'target_runtime', runtime_seconds: 120 },
    { signal }
  );
});
it('forwards the status read signal and validates the response', async () => {
  vi.mocked(apiClient.get).mockResolvedValue({
    data: { ...runningStatus(), run: null },
  });
  await expect(simulationRunApi.get()).rejects.toThrow();
  expect(apiClient.get).toHaveBeenCalledWith('/api/simulation/run', {
    signal: undefined,
  });
});
