import { afterEach, expect, it, vi } from 'vitest';
import apiClient from './api-client';
import {
  getOperatorEvents,
  readEventSnapshot,
  acknowledgeOperatorEvent,
} from './operatorEvents';
import { eventFixture, eventSnapshot } from '@/test/operator-event-fixtures';
afterEach(() => vi.restoreAllMocks());
it('uses the existing HTTP boundary with cancellation and frozen acknowledgment headers', async () => {
  const signal = new AbortController().signal;
  const get = vi
    .spyOn(apiClient, 'get')
    .mockResolvedValue({ data: eventSnapshot() });
  await getOperatorEvents('mission-a', 'cursor', signal);
  expect(get).toHaveBeenCalledWith('/api/v2/operator/events', {
    params: {
      mission_id: 'mission-a',
      cursor: 'cursor',
      include_history: true,
    },
    signal,
  });
  const body = {
    schema_version: 1 as const,
    occurrence_id: 'occurrence',
    severity_generation: 2,
    snapshot_token: 'token',
  };
  const post = vi
    .spyOn(apiClient, 'post')
    .mockResolvedValue({ data: { acknowledgment_id: 'ack' } });
  await acknowledgeOperatorEvent(body, 'key', 'epoch');
  expect(post).toHaveBeenCalledWith(
    '/api/v2/operator/events/acknowledge',
    body,
    { headers: { 'Idempotency-Key': 'key', 'X-Operator-Store-Epoch': 'epoch' } }
  );
});
it('assembles pinned pages before publishing and rejects mismatched sources', async () => {
  const get = vi
    .spyOn(apiClient, 'get')
    .mockResolvedValueOnce({
      data: eventSnapshot({ cursor: 'next', truncated: true }),
    })
    .mockResolvedValueOnce({
      data: eventSnapshot({ events: [eventFixture({ event_id: 'second' })] }),
    });
  expect(
    (await readEventSnapshot('mission-a')).events.map((e) => e.event_id)
  ).toEqual(['event-a', 'second']);
  get
    .mockResolvedValueOnce({
      data: eventSnapshot({ cursor: 'next', truncated: true }),
    })
    .mockResolvedValueOnce({
      data: eventSnapshot({ api_epoch: 'another-epoch' }),
    });
  await expect(readEventSnapshot('mission-a')).rejects.toThrow(
    'Event snapshot changed'
  );
});
