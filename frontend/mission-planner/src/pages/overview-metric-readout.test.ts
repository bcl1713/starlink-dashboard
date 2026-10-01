import { describe, expect, it } from 'vitest';
import type { StatusResponse } from '../services/status';
import { OVERVIEW_METRIC_GRAPHS } from './overview-metric-history';
import {
  networkStatusState,
  statusMetricReadout,
  type MetricReadout,
} from './overview-metric-readout';

function statusFixture(): StatusResponse {
  return {
    timestamp: '1970-01-01T00:01:45.000Z',
    metric_availability: {
      latency_ms: true,
      throughput_down_mbps: true,
      throughput_up_mbps: true,
      packet_loss_percent: true,
      obstruction_percent: true,
    },
    network: {
      latency_ms: 7,
      throughput_down_mbps: 0,
      throughput_up_mbps: 2,
      packet_loss_percent: 0.2,
    },
    obstruction: { obstruction_percent: 3 },
  };
}

function project(
  status: StatusResponse | undefined,
  nowMs = 109_000,
  failed = false
) {
  return OVERVIEW_METRIC_GRAPHS.map((descriptor) =>
    statusMetricReadout(status, descriptor, nowMs, failed)
  );
}

// These cases catch wrong source-field mapping, request-time freshness,
// truthiness-based zero filtering, and off-by-one freshness boundaries.
describe('status metric readout', () => {
  it.each([
    ['latency', 7],
    ['downlink', 0],
    ['uplink', 2],
    ['packet-loss', 0.2],
    ['obstruction', 3],
  ] as const)('projects %s from the collected status sample', (id, value) => {
    const descriptor = OVERVIEW_METRIC_GRAPHS.find((graph) => graph.id === id)!;
    expect(
      statusMetricReadout(statusFixture(), descriptor, 109_000, false)
    ).toEqual({
      value,
      observedAtMs: 105_000,
      ageMs: 4_000,
      state: 'fresh',
    });
    expect(
      statusMetricReadout(statusFixture(), descriptor, 110_000, false)
    ).toEqual({
      value,
      observedAtMs: 105_000,
      ageMs: 5_000,
      state: 'stale',
    });
  });

  it.each([NaN, Infinity, -Infinity, null, undefined, '7'])(
    'rejects unusable source value %s',
    (value) => {
      const status = statusFixture();
      status.network!.latency_ms = value as never;
      const readouts = project(status);
      expect(readouts[0]).toBeNull();
      expect(networkStatusState(readouts)).toBe('partial');
    }
  );

  it.each([false, undefined, 1, 'true'])(
    'requires explicit true provenance rather than %s',
    (flag) => {
      const status = statusFixture();
      status.metric_availability!.throughput_down_mbps = flag as never;
      expect(project(status)[1]).toBeNull();
      expect(project(statusFixture())[1]).toEqual({
        value: 0,
        observedAtMs: 105_000,
        ageMs: 4_000,
        state: 'fresh',
      });
    }
  );

  it('fails closed for a legacy response without the availability map', () => {
    const status = statusFixture();
    delete status.metric_availability;
    expect(project(status)).toEqual([null, null, null, null, null]);
  });

  it('does not substitute missing source fields with zero', () => {
    const status = statusFixture();
    status.network = {};
    status.obstruction = {};
    expect(project(status)).toEqual([null, null, null, null, null]);
    expect(networkStatusState(project(status))).toBe('unavailable');
  });

  it('handles missing source containers without inventing observations', () => {
    const status = statusFixture();
    delete status.network;
    delete status.obstruction;
    expect(project(status)).toEqual([null, null, null, null, null]);
  });

  it.each(['1970-01-01T00:01:50.000Z', 'not-a-timestamp', '', undefined, null])(
    'rejects future, malformed or absent timestamp %s',
    (timestamp) => {
      const status = statusFixture();
      status.timestamp = timestamp as never;
      expect(project(status)).toEqual([null, null, null, null, null]);
    }
  );

  it.each([NaN, Infinity, -Infinity])(
    'rejects an invalid observation clock %s',
    (nowMs) => {
      expect(project(statusFixture(), nowMs)).toEqual([
        null,
        null,
        null,
        null,
        null,
      ]);
    }
  );

  it('returns unavailable before any status response exists', () => {
    expect(project(undefined)).toEqual([null, null, null, null, null]);
    expect(networkStatusState(project(undefined))).toBe('unavailable');
  });

  it('maps by descriptor id, not by the Prometheus graph metric', () => {
    expect(
      statusMetricReadout(
        statusFixture(),
        {
          ...OVERVIEW_METRIC_GRAPHS[0],
          metric: 'unrelated_history_key',
        },
        109_000,
        false
      )?.value
    ).toBe(7);
    expect(
      statusMetricReadout(
        statusFixture(),
        {
          ...OVERVIEW_METRIC_GRAPHS[0],
          id: 'unknown',
        },
        109_000,
        false
      )
    ).toBeNull();
  });

  it('marks last-good observations stale when the status request failed', () => {
    const readouts = project(statusFixture(), 109_000, true);
    expect(readouts).toEqual([
      { value: 7, observedAtMs: 105_000, ageMs: 4_000, state: 'stale' },
      { value: 0, observedAtMs: 105_000, ageMs: 4_000, state: 'stale' },
      { value: 2, observedAtMs: 105_000, ageMs: 4_000, state: 'stale' },
      { value: 0.2, observedAtMs: 105_000, ageMs: 4_000, state: 'stale' },
      { value: 3, observedAtMs: 105_000, ageMs: 4_000, state: 'stale' },
    ]);
    expect(networkStatusState(readouts)).toBe('stale');
  });
});

// These cases catch aggregators that hide missing metrics or stale observations.
describe('network status state', () => {
  it('reports fresh only when all projected metrics are fresh', () => {
    expect(networkStatusState(project(statusFixture()))).toBe('fresh');
  });

  it('reports stale when every metric reaches the collection-age boundary', () => {
    expect(networkStatusState(project(statusFixture(), 110_000))).toBe('stale');
  });

  it('reports partial for mixed fresh and stale observations', () => {
    const readouts = project(statusFixture());
    readouts[0] = { ...readouts[0]!, state: 'stale' };
    expect(networkStatusState(readouts)).toBe('partial');
  });

  it('reports partial for stale observations mixed with unavailable metrics', () => {
    const readouts = project(statusFixture(), 110_000);
    readouts[0] = null;
    expect(networkStatusState(readouts)).toBe('partial');
  });

  it.each([[], [null, null, null, null, null]] as (MetricReadout | null)[][])(
    'reports unavailable without any observation (%s)',
    (...readouts) => {
      expect(networkStatusState(readouts)).toBe('unavailable');
    }
  );
});
