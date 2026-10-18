import { afterEach, expect, it, vi } from 'vitest';
import * as api from '@/services/operator';
import { health, page, record } from '@/test/operator-fixtures';
import { readTrainingRecords } from './readTrainingRecords';
const identity = {
  fixtureVersion: 1,
  origin: 'http://localhost',
  storeId: 'store',
  epoch: 'epoch-a',
  missionId: 'mission-a',
};
afterEach(() => vi.restoreAllMocks());
it('rereads all pages/history on demand and validates the store again', async () => {
  const saved = {
    ...record,
    provenance: { ...record.provenance, source_mode: 'simulation' as const },
  };
  vi.spyOn(api, 'readOperatorRecords')
    .mockResolvedValueOnce({ ...page([saved]), cursor: 'next' })
    .mockResolvedValueOnce(page([]));
  vi.spyOn(api, 'readOperatorHistory').mockResolvedValue(page([saved]));
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue({
    ...health,
    source_mode: 'simulation',
    simulation_run_id: 'training',
  });
  expect(
    (await readTrainingRecords(identity, 'training', [])).outcomes
  ).toContain('scoped-note');
  expect(api.readOperatorRecords).toHaveBeenCalledTimes(2);
});
it('refuses repeated cursors and an epoch change without claiming completion', async () => {
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue({
    ...page(),
    cursor: 'same',
  });
  await expect(readTrainingRecords(identity, 'training', [])).rejects.toThrow(
    /pagination/
  );
  vi.mocked(api.readOperatorRecords).mockResolvedValue(page());
  vi.spyOn(api, 'readOperatorHistory').mockResolvedValue(page());
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue({
    ...health,
    api_epoch: 'changed',
  });
  await expect(readTrainingRecords(identity, 'training', [])).rejects.toThrow(
    /changed/
  );
});
