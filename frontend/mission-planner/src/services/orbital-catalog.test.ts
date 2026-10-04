import { beforeEach, expect, it, vi } from 'vitest';
import apiClient from './api-client';
import { orbitalCatalogApi } from './orbital-catalog';

vi.mock('./api-client', () => ({
  default: { get: vi.fn(), put: vi.fn(), delete: vi.fn(), post: vi.fn() },
}));
beforeEach(() => vi.resetAllMocks());

it('acquires a lease, scopes catalog to viewer and forwards cancellation', async () => {
  const signal = new AbortController().signal;
  vi.mocked(apiClient.put).mockResolvedValue({
    data: { expires_at: '2026-10-04T12:01:15Z' },
  });
  expect((await orbitalCatalogApi.acquire('viewer-a', signal)).expires_at).toBe(
    '2026-10-04T12:01:15Z'
  );
  const envelope = {
    objects: [],
    generation: '',
    acquired_at: null,
    last_attempt_at: null,
    retry_after_at: null,
    suspended: false,
    rejected_count: 0,
    truncated_count: 0,
    eligible_count: 0,
    status: 'loading',
  };
  vi.mocked(apiClient.get).mockResolvedValue({ data: envelope });
  await expect(orbitalCatalogApi.catalog('viewer-a', signal)).resolves.toEqual(
    envelope
  );
  expect(apiClient.get).toHaveBeenCalledWith('/api/orbital/catalog', {
    params: { viewer_id: 'viewer-a' },
    signal,
  });
  await orbitalCatalogApi.release('viewer-a');
  expect(apiClient.delete).toHaveBeenCalledWith(
    '/api/orbital/viewers/viewer-a'
  );
});

it.each([
  {},
  { objects: [], suspended: 'false' },
  { objects: Array(16385).fill({}) },
])('rejects malformed and oversized catalog %j', async (data) => {
  vi.mocked(apiClient.get).mockResolvedValue({ data });
  await expect(orbitalCatalogApi.catalog('v')).rejects.toThrow(
    'Invalid orbital catalog'
  );
});

it('diagnostics and resume use no viewer lease', async () => {
  vi.mocked(apiClient.get).mockResolvedValue({ data: { status: 'loading' } });
  vi.mocked(apiClient.post).mockResolvedValue({ data: { status: 'loading' } });
  await orbitalCatalogApi.status();
  await orbitalCatalogApi.resume();
  expect(apiClient.put).not.toHaveBeenCalled();
  expect(apiClient.get).toHaveBeenCalledWith('/api/orbital/status', {
    signal: undefined,
  });
  expect(apiClient.post).toHaveBeenCalledWith('/api/orbital/provider/resume');
});
