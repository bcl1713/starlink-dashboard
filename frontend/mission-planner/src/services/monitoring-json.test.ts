import axios, { CanceledError } from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from './api-client';
import {
  getGroundEntryPoint,
  getMonitoringHistory,
  getStatus,
} from './monitoring';
import { OverviewDataValidationError } from '../types/monitoring';

vi.mock('./api-client', () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

const getMock = vi.mocked(apiClient.get);
const aware = '2026-08-29T12:34:56.789Z';

const statusPayload = {
  timestamp: aware,
  position: {
    latitude: 39.7392,
    longitude: -104.9903,
    altitude: -12.5,
    speed: 450,
    heading: 360,
  },
  network: {
    latency_ms: 23.5,
    throughput_down_mbps: 125,
    throughput_up_mbps: 18,
    packet_loss_percent: 0,
  },
  obstruction: {
    obstruction_percent: 2.5,
  },
  environmental: {
    signal_quality_percent: 99.1,
    uptime_seconds: 120,
    temperature_celsius: null,
  },
};

const historySeriesNames = [
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
  series: historySeriesNames.map((name, index) => ({
    name,
    samples: [
      { timestamp: `2026-08-29T12:00:0${index}Z`, value: index },
      { timestamp: `2026-08-29T12:00:1${index}Z`, value: null },
    ],
  })),
};

const gepAvailablePayload = {
  available: true,
  observed_at: '2026-08-29T12:30:00+00:00',
  generated_at: aware,
  display: 'Denver, CO, US',
  city: '',
  region: 'CO',
  country: 'US',
  latitude: 39.7392,
  longitude: -104.9903,
};

function respond(data: unknown) {
  getMock.mockResolvedValueOnce({ data });
}

async function expectValidation(
  call: () => Promise<unknown>,
  source: 'status' | 'monitoring-history' | 'ground-entry-point'
) {
  try {
    await call();
    throw new Error('expected validation error');
  } catch (error) {
    expect(error).toBeInstanceOf(OverviewDataValidationError);
    expect(error).toMatchObject({
      name: 'OverviewDataValidationError',
      code: 'invalid_overview_data',
      source,
      message: `Invalid overview data: ${source}`,
    });
    expect(Object.keys(error as object)).toEqual(['name', 'code', 'source']);
    expect(Object.prototype.hasOwnProperty.call(error, 'cause')).toBe(false);
  }
}

beforeEach(() => {
  getMock.mockReset();
});

describe('monitoring JSON services', () => {
  it('gets status with exact request, signal identity, and timestamp text', async () => {
    const signal = new AbortController().signal;
    respond(statusPayload);

    await expect(getStatus(signal)).resolves.toEqual(statusPayload);

    expect(getMock).toHaveBeenCalledWith('/api/status', { signal });
  });

  it('rejects invalid status shapes without coercion or extras', async () => {
    for (const bad of [
      { ...statusPayload, timestamp: '2026-08-29T12:34:56' },
      {
        ...statusPayload,
        position: { ...statusPayload.position, latitude: 91 },
      },
      { ...statusPayload, position: { ...statusPayload.position, speed: -1 } },
      {
        ...statusPayload,
        network: {
          ...statusPayload.network,
          latency_ms: Number.POSITIVE_INFINITY,
        },
      },
      {
        ...statusPayload,
        environmental: {
          ...statusPayload.environmental,
          signal_quality_percent: '99',
        },
      },
      { ...statusPayload, extra: true },
    ]) {
      respond(bad);
      await expectValidation(() => getStatus(), 'status');
    }
  });

  it('gets monitoring history with exact params and ordered series', async () => {
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

  it('rejects malformed history contracts', async () => {
    const duplicate = {
      ...historyPayload,
      series: historyPayload.series.map((series, index) =>
        index === 1 ? { ...series, name: 'latitude_degrees' } : series
      ),
    };
    const nonMonotonic = {
      ...historyPayload,
      series: historyPayload.series.map((series, index) =>
        index === 0
          ? {
              ...series,
              samples: [
                { timestamp: '2026-08-29T12:00:01Z', value: 1 },
                { timestamp: '2026-08-29T12:00:00Z', value: 2 },
              ],
            }
          : series
      ),
    };

    for (const bad of [
      { ...historyPayload, range_seconds: 59 },
      { ...historyPayload, step_seconds: 61 },
      { ...historyPayload, generated_at: '2026-08-29T12:34:56' },
      { ...historyPayload, series: historyPayload.series.slice(1) },
      duplicate,
      nonMonotonic,
      {
        ...historyPayload,
        series: historyPayload.series.map((series) => ({
          ...series,
          samples: [{ timestamp: aware, value: Number.NaN }],
        })),
      },
    ]) {
      respond(bad);
      await expectValidation(
        () => getMonitoringHistory(),
        'monitoring-history'
      );
    }
  });

  it('parses ground entry point discriminants', async () => {
    respond(gepAvailablePayload);
    await expect(getGroundEntryPoint()).resolves.toEqual(gepAvailablePayload);

    const unavailable = {
      available: false,
      observed_at: null,
      generated_at: aware,
      display: null,
      city: null,
      region: null,
      country: null,
      latitude: null,
      longitude: null,
    };
    respond(unavailable);
    await expect(getGroundEntryPoint()).resolves.toEqual(unavailable);
  });

  it('rejects invalid ground entry point variants', async () => {
    for (const bad of [
      { ...gepAvailablePayload, public_ip: '203.0.113.1' },
      { ...gepAvailablePayload, generated_at: '2026-08-29T12:34:56' },
      { ...gepAvailablePayload, latitude: null },
      { ...gepAvailablePayload, longitude: 181 },
      {
        ...gepAvailablePayload,
        available: false,
        observed_at: null,
        display: null,
        city: null,
        region: null,
        country: null,
        latitude: null,
      },
    ]) {
      respond(bad);
      await expectValidation(() => getGroundEntryPoint(), 'ground-entry-point');
    }
  });

  it('unwraps cancellation and preserves ordinary transport failures', async () => {
    const directCancel = new CanceledError('stopped');
    getMock.mockRejectedValueOnce(directCancel);
    await expect(getStatus()).rejects.toBe(directCancel);
    expect(axios.isCancel(directCancel)).toBe(true);

    const wrapped = new Error('api error', {
      cause: new CanceledError('wrapped'),
    });
    getMock.mockRejectedValueOnce(wrapped);
    await expect(getStatus()).rejects.toBe(wrapped.cause);

    const transport = { response: { status: 502 } };
    getMock.mockRejectedValueOnce(transport);
    await expect(getStatus()).rejects.toBe(transport);
  });
});
