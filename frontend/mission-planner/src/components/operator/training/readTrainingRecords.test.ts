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
it('reads the history of learner-edited prerequisites while leaving untouched seed rows uncredited', async () => {
  const original = {
    ...record,
    record_type: 'call' as const,
    provenance: { ...record.provenance, source_mode: 'simulation' as const },
    time: {
      ...record.time,
      occurred_at: null,
      ended_at: null,
      precision: 'unknown' as const,
      end_state: 'unknown' as const,
      planned_start_at: '2026-10-18T16:00:00Z',
    },
    payload: {
      ...record.payload,
      entry_type: 'call' as const,
      status: 'scheduled' as const,
      conference_id: null,
    },
  };
  const current = {
    ...original,
    version: 2,
    previous_version: 1,
    command_id: 'edited',
    journal_seq: 2,
    time: { ...original.time, planned_start_at: '2026-10-18T17:00:00Z' },
  };
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue({
    ...page([current]),
    H: 2,
  });
  vi.spyOn(api, 'readOperatorHistory').mockResolvedValue({
    ...page([original, current]),
    H: 2,
  });
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue({
    ...health,
    source_mode: 'simulation',
    simulation_run_id: 'training',
  });
  const evidence = await readTrainingRecords(identity, 'training', [
    record.record_id,
  ]);
  expect(api.readOperatorHistory).toHaveBeenCalledWith(
    record.record_id,
    undefined
  );
  expect(evidence.outcomes).toContain('call-rescheduled');
  expect(evidence.outcomes).not.toContain('call-created');
});
