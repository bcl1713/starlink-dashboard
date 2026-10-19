import { afterEach, expect, it, vi } from 'vitest';
import apiClient from './api-client';
import { missionsApi } from './missions';
afterEach(() => vi.restoreAllMocks());
it('bounds a mission detail read and forwards query cancellation without changing the mission payload', async () => {
  const mission = { id: 'fictional', metadata: { keep: 'original' }, legs: [] };
  const get = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: mission });
  const controller = new AbortController();
  expect(await missionsApi.get('fictional', controller.signal)).toBe(mission);
  expect(get).toHaveBeenCalledWith('/api/v2/missions/fictional', {
    signal: controller.signal,
    timeout: 10_000,
  });
});
