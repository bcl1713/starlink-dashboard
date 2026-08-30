import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from './api-client';
import { getGroundEntryPoint } from './monitoring';

vi.mock('./api-client', () => ({ apiClient: { get: vi.fn() } }));

const getMock = vi.mocked(apiClient.get);
const aware = '2026-08-29T12:34:56Z';
const available = {
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

beforeEach(() => getMock.mockReset());

function respond(data: unknown) {
  getMock.mockResolvedValueOnce({ data });
}

describe('ground entry point overview service', () => {
  it('requests the exact endpoint and parses available/unavailable variants', async () => {
    const signal = new AbortController().signal;
    respond(available);
    await expect(getGroundEntryPoint(signal)).resolves.toEqual(available);
    expect(getMock).toHaveBeenCalledWith('/api/monitoring/ground-entry-point', {
      signal,
    });

    respond(unavailable);
    await expect(getGroundEntryPoint()).resolves.toEqual(unavailable);
  });

  it('rejects malformed discriminants, coordinates, timestamps, and extras', async () => {
    const invalid = [
      { ...available, public_ip: '203.0.113.1' },
      { ...available, ip: '203.0.113.1' },
      { ...available, generated_at: '2026-08-29T12:34:56' },
      { ...available, observed_at: null },
      { ...available, display: null },
      { ...available, latitude: null },
      { ...available, longitude: null },
      { ...available, latitude: 91 },
      { ...available, longitude: 181 },
      { ...unavailable, display: 'Denver' },
      { ...unavailable, latitude: 39 },
    ];

    for (const payload of invalid) {
      respond(payload);
      await expect(getGroundEntryPoint()).rejects.toMatchObject({
        code: 'invalid_overview_data',
        source: 'ground-entry-point',
      });
    }
  });
});
