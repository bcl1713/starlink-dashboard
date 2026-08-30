import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from './api-client';
import { getGroundEntryPoint } from './monitoring';
import {
  availableGep,
  missing,
  setAt,
  unavailableGep,
  withResponse,
} from './monitoring-test-fixtures';

vi.mock('./api-client', () => ({ apiClient: { get: vi.fn() } }));

const getMock = vi.mocked(apiClient.get);

beforeEach(() => getMock.mockReset());

function respond(data: unknown) {
  getMock.mockResolvedValueOnce(withResponse(data));
}

async function expectGepInvalid(payload: unknown) {
  respond(payload);
  await expect(getGroundEntryPoint()).rejects.toMatchObject({
    code: 'invalid_overview_data',
    source: 'ground-entry-point',
  });
}

describe('ground entry point overview service', () => {
  it('requests the exact endpoint and parses available/unavailable variants', async () => {
    const signal = new AbortController().signal;
    respond(availableGep);
    await expect(getGroundEntryPoint(signal)).resolves.toEqual(availableGep);
    expect(getMock).toHaveBeenCalledWith('/api/monitoring/ground-entry-point', {
      signal,
    });

    respond(unavailableGep);
    await expect(getGroundEntryPoint()).resolves.toEqual(unavailableGep);
  });

  it('rejects every unavailable non-null field independently', async () => {
    const nonNulls = {
      observed_at: '2026-08-29T12:30:00+00:00',
      display: 'Denver',
      city: '',
      region: 'CO',
      country: 'US',
      latitude: 39,
      longitude: -104,
    } as const;

    for (const [field, value] of Object.entries(nonNulls)) {
      await expectGepInvalid(setAt(unavailableGep, [field], value));
    }
  });

  it('rejects available nulls, paired coordinate failures, ranges, and extras', async () => {
    const invalid = [
      setAt(availableGep, ['available'], 'true'),
      setAt(availableGep, ['available'], missing),
      setAt(availableGep, ['observed_at'], null),
      setAt(availableGep, ['observed_at'], '2026-08-29T12:30:00'),
      setAt(availableGep, ['display'], null),
      setAt(availableGep, ['display'], 1),
      setAt(availableGep, ['city'], null),
      setAt(availableGep, ['city'], 1),
      setAt(availableGep, ['region'], null),
      setAt(availableGep, ['region'], 1),
      setAt(availableGep, ['country'], null),
      setAt(availableGep, ['country'], 1),
      setAt(availableGep, ['latitude'], null),
      setAt(availableGep, ['longitude'], null),
      setAt(availableGep, ['latitude'], '39'),
      setAt(availableGep, ['longitude'], '-104'),
      setAt(availableGep, ['latitude'], NaN),
      setAt(availableGep, ['longitude'], Infinity),
      setAt(availableGep, ['latitude'], -91),
      setAt(availableGep, ['latitude'], 91),
      setAt(availableGep, ['longitude'], -181),
      setAt(availableGep, ['longitude'], 181),
      setAt(availableGep, ['generated_at'], '2026-08-29T12:34:56'),
      setAt(availableGep, ['generated_at'], missing),
      setAt(availableGep, ['public_ip'], '203.0.113.1'),
      setAt(availableGep, ['ip'], '203.0.113.1'),
      setAt(availableGep, ['extra'], true),
    ];

    for (const payload of invalid) await expectGepInvalid(payload);
  });
});
