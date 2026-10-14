import { afterEach, expect, it, vi } from 'vitest';
import { missionsApi } from './missions';
import { apiClient } from './api-client';
import type { MissionLeg } from '../types/mission';
afterEach(() => vi.restoreAllMocks());
it('sends optional managed CAS for leg PUT and DELETE', async () => {
  const put = vi
    .spyOn(apiClient, 'put')
    .mockResolvedValue({ data: { leg: {} } });
  const remove = vi
    .spyOn(apiClient, 'delete')
    .mockResolvedValue({ data: null });
  const cas = { expected_revision: 7, input_identity: 'source' };
  await missionsApi.updateLeg('m', 'l', {} as MissionLeg, cas);
  await missionsApi.deleteLeg('m', 'l', cas);
  expect(put).toHaveBeenCalledWith(
    '/api/v2/missions/m/legs/l',
    {},
    { params: cas }
  );
  expect(remove).toHaveBeenCalledWith('/api/v2/missions/m/legs/l', {
    params: cas,
  });
});
