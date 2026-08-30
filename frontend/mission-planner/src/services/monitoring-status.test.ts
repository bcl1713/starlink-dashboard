import axios, { CanceledError } from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from './api-client';
import { getStatus } from './monitoring';
import {
  missing,
  setAt,
  statusPayload,
  withResponse,
} from './monitoring-test-fixtures';
import { OverviewDataValidationError } from '../types/monitoring';

vi.mock('./api-client', () => ({ apiClient: { get: vi.fn() } }));

const getMock = vi.mocked(apiClient.get);

beforeEach(() => getMock.mockReset());

function respond(data: unknown) {
  getMock.mockResolvedValueOnce(withResponse(data));
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
    respond({
      ...statusPayload,
      environmental: {
        ...statusPayload.environmental,
        temperature_celsius: null,
      },
    });

    await expect(getStatus(signal)).resolves.toMatchObject({
      timestamp: statusPayload.timestamp,
    });

    expect(getMock).toHaveBeenCalledWith('/api/status', { signal });
  });

  it('rejects missing, extras, coercion, nonfinite, and bounds per field', async () => {
    const invalid: unknown[] = [
      setAt(statusPayload, ['timestamp'], '2026-08-29T12:34:56'),
      setAt(statusPayload, ['timestamp'], missing),
      setAt(statusPayload, ['position'], missing),
      setAt(statusPayload, ['network'], missing),
      setAt(statusPayload, ['obstruction'], missing),
      setAt(statusPayload, ['environmental'], missing),
      setAt(statusPayload, ['extra'], true),
    ];
    const numericCases = [
      [['position', 'latitude'], -91, 91, NaN, '39'],
      [['position', 'longitude'], -181, 181, Infinity, '104'],
      [['position', 'altitude'], null, undefined, NaN, '1'],
      [['position', 'speed'], -1, undefined, Infinity, '1'],
      [['position', 'heading'], -1, 361, NaN, '1'],
      [['network', 'latency_ms'], -1, undefined, Infinity, '1'],
      [['network', 'throughput_down_mbps'], -1, undefined, NaN, '1'],
      [['network', 'throughput_up_mbps'], -1, undefined, Infinity, '1'],
      [['network', 'packet_loss_percent'], -0.1, 100.1, NaN, '1'],
      [['obstruction', 'obstruction_percent'], -0.1, 100.1, Infinity, '1'],
      [['environmental', 'signal_quality_percent'], -0.1, 100.1, NaN, '1'],
      [['environmental', 'uptime_seconds'], -1, undefined, Infinity, '1'],
      [['environmental', 'temperature_celsius'], undefined, Infinity, NaN, '1'],
    ] as const;

    for (const [path, ...values] of numericCases) {
      invalid.push(setAt(statusPayload, path, missing));
      for (const value of values)
        invalid.push(setAt(statusPayload, path, value));
    }
    invalid.push(
      setAt(statusPayload, ['position', 'extra'], true),
      setAt(statusPayload, ['network', 'extra'], true),
      setAt(statusPayload, ['obstruction', 'extra'], true),
      setAt(statusPayload, ['environmental', 'extra'], true)
    );

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
