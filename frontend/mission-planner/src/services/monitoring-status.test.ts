import axios, { CanceledError } from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from './api-client';
import { getStatus } from './monitoring';
import { OverviewDataValidationError } from '../types/monitoring';

vi.mock('./api-client', () => ({ apiClient: { get: vi.fn() } }));

const getMock = vi.mocked(apiClient.get);
const aware = '2026-08-29T12:34:56.789Z';
const statusPayload = {
  timestamp: aware,
  position: {
    latitude: -90,
    longitude: 180,
    altitude: -12.5,
    speed: 0,
    heading: 360,
  },
  network: {
    latency_ms: 23.5,
    throughput_down_mbps: 125,
    throughput_up_mbps: 18,
    packet_loss_percent: 100,
  },
  obstruction: { obstruction_percent: 0 },
  environmental: {
    signal_quality_percent: 99.1,
    uptime_seconds: 120,
    temperature_celsius: null,
  },
};

beforeEach(() => getMock.mockReset());

function respond(data: unknown) {
  getMock.mockResolvedValueOnce({ data });
}

async function expectStatusInvalid(payload: unknown) {
  respond(payload);
  try {
    await getStatus();
    throw new Error('expected validation error');
  } catch (error) {
    expect(error).toBeInstanceOf(OverviewDataValidationError);
    expect(error).toMatchObject({
      name: 'OverviewDataValidationError',
      code: 'invalid_overview_data',
      source: 'status',
      message: 'Invalid overview data: status',
    });
    expect(Object.keys(error as object)).toEqual(['name', 'code', 'source']);
    expect(Object.prototype.hasOwnProperty.call(error, 'cause')).toBe(false);
  }
}

describe('status overview service', () => {
  it('requests /api/status with signal identity and preserves timestamps', async () => {
    const signal = new AbortController().signal;
    respond(statusPayload);

    await expect(getStatus(signal)).resolves.toEqual(statusPayload);

    expect(getMock).toHaveBeenCalledWith('/api/status', { signal });
  });

  it('rejects malformed strict status payloads', async () => {
    const invalid = [
      { ...statusPayload, timestamp: '2026-08-29T12:34:56' },
      { ...statusPayload, extra: true },
      { ...statusPayload, position: { ...statusPayload.position, yaw: 1 } },
      {
        ...statusPayload,
        position: { ...statusPayload.position, latitude: 91 },
      },
      { ...statusPayload, position: { ...statusPayload.position, speed: -1 } },
      {
        ...statusPayload,
        position: { ...statusPayload.position, heading: 361 },
      },
      {
        ...statusPayload,
        position: { ...statusPayload.position, altitude: NaN },
      },
      {
        ...statusPayload,
        network: { ...statusPayload.network, latency_ms: Infinity },
      },
      {
        ...statusPayload,
        network: { ...statusPayload.network, packet_loss_percent: -0.1 },
      },
      {
        ...statusPayload,
        obstruction: { ...statusPayload.obstruction, obstruction_percent: 101 },
      },
      {
        ...statusPayload,
        environmental: {
          ...statusPayload.environmental,
          signal_quality_percent: '99',
        },
      },
      {
        ...statusPayload,
        environmental: { ...statusPayload.environmental, uptime_seconds: -1 },
      },
      { ...statusPayload, environmental: { uptime_seconds: 1 } },
    ];

    for (const payload of invalid) await expectStatusInvalid(payload);
  });

  it('unwraps cancellation and preserves transport failures by identity', async () => {
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
