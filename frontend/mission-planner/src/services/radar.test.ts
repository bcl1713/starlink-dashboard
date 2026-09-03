import { describe, expect, it, vi } from 'vitest';
import { fetchRadarMetadata, radarMetadataUrl } from './monitoring';

describe('fetchRadarMetadata', () => {
  it('uses the fixed same-origin metadata lane and rejects external tile templates', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          available: true,
          tile_url: '/api/weather/radar/rainviewer/{z}/{x}/{y}.png?frame=123',
        }),
        { headers: { 'Content-Type': 'application/json' } }
      )
    );
    vi.stubGlobal('fetch', fetchMock);

    await expect(fetchRadarMetadata()).resolves.toEqual({
      available: true,
      tileUrl: '/api/weather/radar/rainviewer/{z}/{x}/{y}.png?frame=123',
    });
    expect(fetchMock).toHaveBeenCalledWith(
      radarMetadataUrl,
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );
    expect(radarMetadataUrl).toBe('/api/weather/radar/rainviewer/metadata');

    vi.unstubAllGlobals();
  });

  it('rejects a direct RainViewer tile target', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            available: true,
            tile_url:
              'https://tilecache.rainviewer.com/v2/radar/{z}/{x}/{y}.png',
          }),
          { headers: { 'Content-Type': 'application/json' } }
        )
      )
    );

    await expect(fetchRadarMetadata()).rejects.toThrow();

    vi.unstubAllGlobals();
  });
});
