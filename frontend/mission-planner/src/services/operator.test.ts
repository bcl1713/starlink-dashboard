import { afterEach, expect, it, vi } from 'vitest';
import apiClient from './api-client';
import {
  getOperatorHealth,
  readOperatorRecords,
  readOperatorHistory,
  saveOperatorCommand,
} from './operator';
import { health, input, page, record } from '@/test/operator-fixtures';
afterEach(() => vi.restoreAllMocks());
it('uses public envelopes, encoded paths, and exact epoch/key headers without internal fields', async () => {
  const get = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: page() });
  await expect(
    readOperatorRecords(
      { mission_id: 'mission-a', include_removed: true },
      'cursor'
    )
  ).resolves.toEqual(page());
  expect(get).toHaveBeenCalledWith('/api/v2/operator/records', {
    params: {
      mission_id: 'mission-a',
      include_removed: true,
      cursor: 'cursor',
    },
  });
  await readOperatorHistory('a/b', 'next');
  expect(get).toHaveBeenLastCalledWith(
    '/api/v2/operator/records/a%2Fb/history',
    { params: { cursor: 'next' } }
  );
  const post = vi.spyOn(apiClient, 'post').mockResolvedValue({
    data: {
      schema_version: 1,
      command_id: 'receipt',
      saved_records: [record],
    },
  });
  await saveOperatorCommand(
    { operation: 'create', body: input },
    'key',
    'epoch'
  );
  expect(post).toHaveBeenCalledWith('/api/v2/operator/records', input, {
    headers: { 'Idempotency-Key': 'key', 'X-Operator-Store-Epoch': 'epoch' },
  });
});
it('retains enabled health on 503 and propagates disabled 404', async () => {
  vi.spyOn(apiClient, 'get')
    .mockRejectedValueOnce({
      cause: { response: { status: 503, data: { ...health, ready: false } } },
    })
    .mockRejectedValueOnce({ cause: { response: { status: 404 } } });
  await expect(getOperatorHealth()).resolves.toMatchObject({
    enabled: true,
    ready: false,
  });
  await expect(getOperatorHealth()).rejects.toBeTruthy();
});
