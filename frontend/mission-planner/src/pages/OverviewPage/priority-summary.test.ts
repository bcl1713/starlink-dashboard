import { describe, expect, it } from 'vitest';

import { makeOverviewSnapshot } from './OperationalMap/test-fixtures';
import { prioritySummary } from './priority-summary';
import type { OverviewDataSnapshot } from './overview-data-types';

function withTelemetry(
  patch: Partial<OverviewDataSnapshot['telemetry']>,
  latency = 1
): OverviewDataSnapshot {
  const snapshot = makeOverviewSnapshot();
  return {
    ...snapshot,
    telemetry: {
      ...snapshot.telemetry,
      ...patch,
      data:
        'data' in patch
          ? patch.data
          : {
              ...snapshot.telemetry.data!,
              network: {
                ...snapshot.telemetry.data!.network,
                latency_ms: latency,
              },
            },
    },
  };
}

describe('prioritySummary', () => {
  it.each([
    [
      'initial loading',
      { phase: 'initial-loading', data: undefined },
      'loading',
    ],
    [
      'unavailable',
      { availability: 'unavailable', data: undefined },
      'unavailable',
    ],
    ['fresh', {}, 'fresh'],
    ['stale', { phase: 'stale', freshness: 'stale' }, 'stale'],
    ['paused', { phase: 'paused', paused: true }, 'paused'],
    [
      'retained failure',
      {
        phase: 'refreshing',
        error: {
          code: 'request-failed',
          message: 'Source refresh failed.',
        },
      },
      'retained data after refresh failed',
    ],
    ['recovery', { phase: 'ready', error: null }, 'fresh'],
  ] as const)('describes %s telemetry truthfully', (_name, patch, text) => {
    expect(prioritySummary(withTelemetry(patch))).toContain(text);
  });

  it.each([
    [99.9, 'Latency normal below 100 ms'],
    [100, 'Latency Warning at 100 ms'],
    [199.9, 'Latency Warning at 100 ms'],
    [200, 'Latency Critical at 200 ms'],
  ])('describes latency threshold boundary %s', (latency, text) => {
    expect(prioritySummary(withTelemetry({}, latency))).toContain(text);
  });

  it('renders hostile route text as plain summary text', () => {
    const snapshot = makeOverviewSnapshot();
    expect(
      prioritySummary({
        ...snapshot,
        route: {
          ...snapshot.route,
          data: {
            ...snapshot.route.data!,
            west: {
              ...snapshot.route.data!.west,
              route_name: '<script>alert(1)</script>',
              total: 1,
            },
          },
        },
      })
    ).toContain('Active route <script>alert(1)</script>');
  });
});
