import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from './api-client';
import { getMonitoringHistory } from './monitoring';
import { OverviewDataValidationError } from '../types/monitoring';

vi.mock('./api-client', () => ({ apiClient: { get: vi.fn() } }));

const getMock = vi.mocked(apiClient.get);
const aware = '2026-08-29T12:34:56.789123Z';
const metrics = [
  'latitude_degrees',
  'longitude_degrees',
  'latency_ms',
  'throughput_down_mbps',
  'throughput_up_mbps',
  'packet_loss_percent',
] as const;

const historyPayload = {
  generated_at: aware,
  window_start: '2026-08-29T12:00:00-06:00',
  window_end: '2026-08-29T12:30:00-06:00',
  range_seconds: 1800,
  step_seconds: 1,
  series: metrics.map((metric, index) => ({
    metric,
    samples: [
      { timestamp: `2026-08-29T12:00:0${index}.000001Z`, value: index },
      { timestamp: `2026-08-29T12:00:0${index}.000002Z`, value: null },
    ],
  })),
};

beforeEach(() => getMock.mockReset());

function respond(data: unknown) {
  getMock.mockResolvedValueOnce({ data });
}

function withSeries(series: unknown[]) {
  return { ...historyPayload, series };
}

async function expectHistoryInvalid(payload: unknown) {
  respond(payload);
  await expect(getMonitoringHistory()).rejects.toMatchObject({
    name: 'OverviewDataValidationError',
    code: 'invalid_overview_data',
    source: 'monitoring-history',
    message: 'Invalid overview data: monitoring-history',
  });
}

describe('monitoring history overview service', () => {
  it('requests exact params, preserves backend metric serialization and timestamps', async () => {
    const signal = new AbortController().signal;
    respond(historyPayload);

    await expect(
      getMonitoringHistory({ rangeSeconds: 600, stepSeconds: 5, signal })
    ).resolves.toEqual(historyPayload);

    expect(getMock).toHaveBeenCalledWith('/api/monitoring/history', {
      params: { range_seconds: 600, step_seconds: 5 },
      signal,
    });
  });

  it('uses monitoring history defaults', async () => {
    respond(historyPayload);

    await getMonitoringHistory();

    expect(getMock).toHaveBeenCalledWith('/api/monitoring/history', {
      params: { range_seconds: 1800, step_seconds: 1 },
      signal: undefined,
    });
  });

  it('accepts full-precision chronological instants that Date.parse collapses', async () => {
    const precise = withSeries(
      historyPayload.series.map((series, index) =>
        index === 0
          ? {
              ...series,
              samples: [
                { timestamp: '2026-08-29T12:00:00.000001Z', value: 1 },
                { timestamp: '2026-08-29T12:00:00.000002Z', value: 2 },
              ],
            }
          : series
      )
    );
    respond(precise);

    await expect(getMonitoringHistory()).resolves.toEqual(precise);
  });

  it('rejects malformed history contracts including metric order and name keys', async () => {
    const duplicate = withSeries(
      historyPayload.series.map((series, index) =>
        index === 1 ? { ...series, metric: 'latitude_degrees' } : series
      )
    );
    const wrongOrder = withSeries([
      historyPayload.series[1],
      historyPayload.series[0],
      ...historyPayload.series.slice(2),
    ]);
    const nameKey = withSeries(
      historyPayload.series.map(({ metric, ...series }) => ({
        ...series,
        name: metric,
      }))
    );
    const equalOffsetInstants = withSeries([
      {
        ...historyPayload.series[0],
        samples: [
          { timestamp: '2026-08-29T12:00:00Z', value: 1 },
          { timestamp: '2026-08-29T07:00:00-05:00', value: 2 },
        ],
      },
      ...historyPayload.series.slice(1),
    ]);
    const offsetInversion = withSeries([
      {
        ...historyPayload.series[0],
        samples: [
          { timestamp: '2026-08-29T12:00:00+01:00', value: 1 },
          { timestamp: '2026-08-29T11:30:00+01:00', value: 2 },
        ],
      },
      ...historyPayload.series.slice(1),
    ]);

    const invalid = [
      { ...historyPayload, range_seconds: 59 },
      { ...historyPayload, range_seconds: 60.5 },
      { ...historyPayload, step_seconds: 61 },
      { ...historyPayload, generated_at: '2026-08-29T12:34:56' },
      { ...historyPayload, series: historyPayload.series.slice(1) },
      { ...historyPayload, series: [{ ...historyPayload.series[0], x: 1 }] },
      duplicate,
      wrongOrder,
      nameKey,
      equalOffsetInstants,
      offsetInversion,
      withSeries([
        {
          ...historyPayload.series[0],
          samples: [{ timestamp: aware, value: Number.NaN }],
        },
        ...historyPayload.series.slice(1),
      ]),
      withSeries([
        { ...historyPayload.series[0], samples: [{ timestamp: aware }] },
      ]),
      withSeries([
        {
          ...historyPayload.series[0],
          samples: [{ timestamp: '2026-08-29T12:00:00', value: 1 }],
        },
        ...historyPayload.series.slice(1),
      ]),
    ];

    for (const payload of invalid) await expectHistoryInvalid(payload);
  });

  it('emits sanitized validation errors', async () => {
    respond({ ...historyPayload, generated_at: 'naive' });

    try {
      await getMonitoringHistory();
      throw new Error('expected validation error');
    } catch (error) {
      expect(error).toBeInstanceOf(OverviewDataValidationError);
      expect(Object.keys(error as object)).toEqual(['name', 'code', 'source']);
      expect(Object.prototype.hasOwnProperty.call(error, 'cause')).toBe(false);
    }
  });
});
