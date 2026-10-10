/** @vitest-environment jsdom */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from './api-client';
import { planningApi, planningErrorMessage, arRouteSpan } from './planning';
import type { RouteAnchor } from '../types/planning';

afterEach(() => vi.restoreAllMocks());
describe('planning wire contracts', () => {
  it('targets the selected stable expected leg with multipart revision', async () => {
    const post = vi
      .spyOn(apiClient, 'post')
      .mockResolvedValue({ data: { preview_id: 'p' } });
    const file = new File(['synthetic'], 'arbitrary.kml');
    await planningApi.previewRoute('mission', 'expected-3', file, 7);
    expect(post.mock.calls[0][0]).toBe(
      '/api/v2/missions/planning/missions/mission/legs/expected-3/route-previews'
    );
    const form = post.mock.calls[0][1] as FormData;
    expect(form.get('file')).toBe(file);
    expect(form.get('expected_revision')).toBe('7');
  });
  it('saves only the draft with a revision and reloads durable state', async () => {
    const put = vi
      .spyOn(apiClient, 'put')
      .mockResolvedValue({ data: { revision: 8 } });
    const get = vi
      .spyOn(apiClient, 'get')
      .mockResolvedValue({ data: { revision: 8 } });
    expect(
      await planningApi.saveDraft('m', 'l', {
        expected_revision: 7,
        draft: { starshield_enabled: false },
      })
    ).toEqual({ revision: 8 });
    expect(put.mock.calls[0][1]).toEqual({
      expected_revision: 7,
      draft: { starshield_enabled: false },
    });
    expect(await planningApi.read('m')).toEqual({ revision: 8 });
    expect(get.mock.calls[0][0]).toContain('/planning/missions/m');
  });
  it('explains stale saves and enforces the 10 MiB PDF limit before requests', async () => {
    expect(
      planningErrorMessage(
        new Error('conflict', { cause: { response: { status: 409 } } })
      )
    ).toMatch(/reload/i);
    const post = vi.spyOn(apiClient, 'post');
    await expect(
      planningApi.previewItinerary(
        new File([new Uint8Array(10 * 1024 * 1024 + 1)], 'large.pdf')
      )
    ).rejects.toThrow('10 MiB');
    expect(post).not.toHaveBeenCalled();
  });
});
describe('AR route span geometry', () => {
  const anchor = (index: number, fraction: number): RouteAnchor => ({
    route_id: 'route',
    content_hash: 'hash',
    segment_index: index,
    fraction,
    occurrence_id: `segment:${index}:${fraction}`,
    source_time: '2026-10-25T12:00:00Z',
    latitude: index + fraction,
    longitude: 10 + index,
  });
  it('retains intermediate curved route geometry between interpolated anchors', () => {
    expect(
      arRouteSpan(
        [
          [0, 10],
          [1, 14],
          [2, 11],
          [3, 13],
        ],
        anchor(0, 0.5),
        anchor(2, 0.5),
        { route_id: 'route', content_hash: 'hash' }
      )
    ).toEqual([
      [0.5, 10],
      [1, 14],
      [2, 11],
      [2.5, 12],
    ]);
  });
  it('includes exact occurrence endpoints once and rejects old-route anchors', () => {
    expect(
      arRouteSpan(
        [
          [0, 10],
          [1, 14],
          [2, 11],
        ],
        anchor(0, 0),
        anchor(2, 0),
        { route_id: 'route', content_hash: 'hash' }
      )
    ).toEqual([
      [0, 10],
      [1, 14],
      [2, 12],
    ]);
    expect(
      arRouteSpan(
        [
          [0, 10],
          [1, 14],
        ],
        anchor(0, 0),
        anchor(1, 0),
        { route_id: 'new', content_hash: 'hash' }
      )
    ).toEqual([]);
  });
});
