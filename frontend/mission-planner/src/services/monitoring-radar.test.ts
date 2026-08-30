import axios, { AxiosHeaders, CanceledError } from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from './api-client';
import { getRainViewerRadarTile } from './monitoring';

vi.mock('./api-client', () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

const getMock = vi.mocked(apiClient.get);

function pngBytes(size = 16) {
  const bytes = new Uint8Array(size);
  bytes.set([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a].slice(0, size));
  return bytes.buffer;
}

function respond(data: unknown, headers: unknown) {
  getMock.mockResolvedValueOnce({ data, headers });
}

beforeEach(() => {
  getMock.mockReset();
});

describe('RainViewer radar tile service', () => {
  it('requests the exact same-origin PNG tile and parses AxiosHeaders', async () => {
    const signal = new AbortController().signal;
    const bytes = pngBytes();
    respond(
      bytes,
      new AxiosHeaders({
        'Content-Type': 'image/png; charset=binary',
        'X-Radar-Frame-Timestamp': '946684800',
      })
    );

    await expect(
      getRainViewerRadarTile({ z: 2, x: 3, y: 0, signal })
    ).resolves.toEqual({ bytes, frameTimestamp: '946684800' });

    expect(getMock).toHaveBeenCalledWith(
      '/api/weather/radar/rainviewer/2/3/0.png',
      { responseType: 'arraybuffer', signal }
    );
    expect(getMock).toHaveBeenCalledTimes(1);
  });

  it('accepts minimum and maximum valid PNG byte lengths', async () => {
    const minimum = pngBytes(8);
    respond(minimum, goodHeaders());
    await expect(getRainViewerRadarTile({ z: 1, x: 0, y: 0 })).resolves.toEqual(
      { bytes: minimum, frameTimestamp: '946684800' }
    );

    const maximum = pngBytes(2 * 1024 * 1024);
    respond(maximum, goodHeaders());
    await expect(getRainViewerRadarTile({ z: 1, x: 1, y: 1 })).resolves.toEqual(
      { bytes: maximum, frameTimestamp: '946684800' }
    );
  });

  it('parses lowercase plain-object headers and preserves timestamp text', async () => {
    const bytes = pngBytes();
    respond(bytes, {
      'content-type': ' image/png ',
      'x-radar-frame-timestamp': '4102444800',
    });

    await expect(getRainViewerRadarTile({ z: 0, x: 0, y: 0 })).resolves.toEqual(
      {
        bytes,
        frameTimestamp: '4102444800',
      }
    );
  });

  it('rejects invalid XYZ before making a request', async () => {
    for (const coords of [
      { z: -1, x: 0, y: 0 },
      { z: 8, x: 0, y: 0 },
      { z: 2.5, x: 0, y: 0 },
      { z: 2, x: 4, y: 0 },
      { z: 2, x: 0, y: 4 },
      { z: 2, x: Number.POSITIVE_INFINITY, y: 0 },
    ]) {
      await expect(getRainViewerRadarTile(coords)).rejects.toMatchObject({
        name: 'OverviewDataValidationError',
        code: 'invalid_overview_data',
        source: 'rainviewer-radar-tile',
        message: 'Invalid overview data: rainviewer-radar-tile',
      });
    }

    expect(getMock).not.toHaveBeenCalled();
  });

  it('rejects invalid radar binary and headers', async () => {
    for (const response of [
      { data: new Uint8Array(pngBytes()), headers: goodHeaders() },
      { data: pngBytes(7), headers: goodHeaders() },
      { data: pngBytes(2 * 1024 * 1024 + 1), headers: goodHeaders() },
      {
        data: new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8]).buffer,
        headers: goodHeaders(),
      },
      { data: pngBytes(), headers: { 'content-type': 'application/json' } },
      {
        data: pngBytes(),
        headers: {
          'content-type': 'image/png',
        },
      },
      {
        data: pngBytes(),
        headers: {
          'content-type': 'image/png',
          'x-radar-frame-timestamp': 946684800,
        },
      },
      {
        data: pngBytes(),
        headers: {
          'content-type': 'image/png',
          'x-radar-frame-timestamp': ['946684800', '946684801'],
        },
      },
      {
        data: pngBytes(),
        headers: {
          'content-type': 'image/png',
          'x-radar-frame-timestamp': '0946684800',
        },
      },
      {
        data: pngBytes(),
        headers: {
          'content-type': 'image/png',
          'x-radar-frame-timestamp': '946684799',
        },
      },
      {
        data: pngBytes(),
        headers: {
          'content-type': 'image/png',
          'x-radar-frame-timestamp': '4102444801',
        },
      },
      {
        data: pngBytes(),
        headers: {
          'content-type': 'image/png',
          'x-radar-frame-timestamp': '1.5',
        },
      },
      {
        data: pngBytes(),
        headers: {
          'content-type': 'image/png',
          'x-radar-frame-timestamp': '+946684800',
        },
      },
      {
        data: pngBytes(),
        headers: {
          'content-type': 'image/png',
          'x-radar-frame-timestamp': '946684800 ',
        },
      },
      {
        data: pngBytes(),
        headers: {
          'content-type': 'image/png',
          'x-radar-frame-timestamp': '9e8',
        },
      },
    ]) {
      respond(response.data, response.headers);
      await expect(
        getRainViewerRadarTile({ z: 1, x: 0, y: 1 })
      ).rejects.toMatchObject({
        source: 'rainviewer-radar-tile',
      });
    }
  });

  it('unwraps cancellation and preserves non-validation transport failures', async () => {
    const directCancel = new CanceledError('stopped');
    getMock.mockRejectedValueOnce(directCancel);
    await expect(getRainViewerRadarTile({ z: 1, x: 0, y: 0 })).rejects.toBe(
      directCancel
    );
    expect(axios.isCancel(directCancel)).toBe(true);

    const wrapped = new Error('api error', {
      cause: new CanceledError('wrapped'),
    });
    getMock.mockRejectedValueOnce(wrapped);
    await expect(getRainViewerRadarTile({ z: 1, x: 0, y: 0 })).rejects.toBe(
      wrapped.cause
    );

    const status400 = { response: { status: 400 } };
    getMock.mockRejectedValueOnce(status400);
    await expect(getRainViewerRadarTile({ z: 1, x: 0, y: 0 })).rejects.toBe(
      status400
    );
  });
});

function goodHeaders() {
  return {
    'content-type': 'image/png',
    'x-radar-frame-timestamp': '946684800',
  };
}
