import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from './api-client';
import { getMonitoringHistory } from './monitoring';
import {
  historyPayload,
  historyMetrics,
  missing,
  setAt,
  withResponse,
} from './monitoring-test-fixtures';
import { OverviewDataValidationError } from '../types/monitoring';

vi.mock('./api-client', () => ({ apiClient: { get: vi.fn() } }));

const getMock = vi.mocked(apiClient.get);

beforeEach(() => getMock.mockReset());

function respond(data: unknown) {
  getMock.mockResolvedValueOnce(withResponse(data));
}

function withFirstSeriesSamples(
  samples: { timestamp: string; value: number | null }[]
) {
  return setAt(historyPayload, ['series', 0, 'samples'], samples);
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
  it('requests exact params, preserves metric serialization and timestamps', async () => {
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

  it('accepts every required timestamp chronology form without normalizing text', async () => {
    const accepted = [
      ['2026-08-29T12:00Z', '2026-08-29T12:01Z'],
      ['0000-02-29T00:00Z', '0000-03-01T00:00Z'],
      ['0099-12-31T23:59:59Z', '0100-01-01T00:00:00Z'],
      ['1969-12-31T23:59:59.999999Z', '1970-01-01T00:00:00Z'],
      ['2025-12-31T23:30:00-01:00', '2026-01-01T02:00:00+00:00'],
      ['2026-08-29T12:00:00+01:00', '2026-08-29T11:30:00Z'],
      ['2026-08-29T12:00:00.000001Z', '2026-08-29T12:00:00.000002Z'],
      ['2026-08-29T12:00:00.123456789Z', '2026-08-29T12:00:00.123456790Z'],
    ];

    for (const [first, second] of accepted) {
      const payload = withFirstSeriesSamples([
        { timestamp: first, value: 1 },
        { timestamp: second, value: 2 },
      ]);
      respond(payload);
      await expect(getMonitoringHistory()).resolves.toEqual(payload);
    }
  });

  it('rejects equal instants, coercion, bad structure, and bad ranges in isolation', async () => {
    const duplicateMetric = setAt(
      historyPayload,
      ['series', 1, 'metric'],
      historyMetrics[0]
    );
    const wrongOrder = {
      ...historyPayload,
      series: [
        historyPayload.series[1],
        historyPayload.series[0],
        ...historyPayload.series.slice(2),
      ],
    };
    const nameKey = {
      ...historyPayload,
      series: historyPayload.series.map(({ metric, ...series }) => ({
        ...series,
        name: metric,
      })),
    };
    const invalid = [
      setAt(historyPayload, ['range_seconds'], 59),
      setAt(historyPayload, ['range_seconds'], 3601),
      setAt(historyPayload, ['range_seconds'], 60.5),
      setAt(historyPayload, ['range_seconds'], '1800'),
      setAt(historyPayload, ['step_seconds'], 0),
      setAt(historyPayload, ['step_seconds'], 61),
      setAt(historyPayload, ['step_seconds'], 1.5),
      setAt(historyPayload, ['generated_at'], '2026-08-29T12:34:56'),
      setAt(historyPayload, ['window_start'], '2026-08-29T12:34:56'),
      setAt(historyPayload, ['window_end'], '2026-08-29T12:34:56'),
      { ...historyPayload, series: historyPayload.series.slice(1) },
      setAt(historyPayload, ['series', 0, 'extra'], true),
      setAt(historyPayload, ['series', 0, 'samples', 0, 'extra'], true),
      setAt(historyPayload, ['series', 0, 'samples', 0, 'value'], NaN),
      setAt(historyPayload, ['series', 0, 'samples', 0, 'value'], '1'),
      setAt(historyPayload, ['series', 0, 'samples', 0, 'value'], missing),
      setAt(
        historyPayload,
        ['series', 0, 'samples', 0, 'timestamp'],
        '2026-08-29T12:00:00'
      ),
      duplicateMetric,
      wrongOrder,
      nameKey,
      withFirstSeriesSamples([
        { timestamp: '2026-08-29T12:00:00Z', value: 1 },
        { timestamp: '2026-08-29T07:00:00-05:00', value: 2 },
      ]),
      withFirstSeriesSamples([
        { timestamp: '2026-08-29T12:00:00.1Z', value: 1 },
        { timestamp: '2026-08-29T12:00:00.1000Z', value: 2 },
      ]),
      withFirstSeriesSamples([
        { timestamp: '2026-08-29T12:00:00+01:00', value: 1 },
        { timestamp: '2026-08-29T11:30:00+01:00', value: 2 },
      ]),
    ];

    for (const payload of invalid) await expectHistoryInvalid(payload);
  });

  it('emits sanitized validation errors', async () => {
    respond(setAt(historyPayload, ['generated_at'], 'naive'));

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
