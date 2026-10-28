import apiClient from './api-client';
import type {
  AckReceipt,
  AckRequest,
  EventSnapshot,
} from '@/types/operatorEvents';
const base = '/api/v2/operator/events';
export async function getOperatorEvents(
  missionId: string,
  cursor?: string,
  signal?: AbortSignal
): Promise<EventSnapshot> {
  return (
    await apiClient.get<EventSnapshot>(base, {
      params: { mission_id: missionId, cursor, include_history: true },
      signal,
    })
  ).data;
}
export async function readEventSnapshot(
  missionId: string,
  signal?: AbortSignal
): Promise<EventSnapshot> {
  const first = await getOperatorEvents(missionId, undefined, signal);
  validatePage(first, missionId);
  const snapshot = { ...first, events: [...first.events] };
  const seen = new Set<string>();
  let cursor = first.cursor;
  while (cursor) {
    if (seen.has(cursor) || seen.size >= 100)
      throw new Error('Event pagination did not advance');
    seen.add(cursor);
    const next = await getOperatorEvents(missionId, cursor, signal);
    validatePage(next, missionId);
    if (
      next.source_mode !== first.source_mode ||
      next.simulation_run_id !== first.simulation_run_id ||
      next.as_of !== first.as_of ||
      next.coverage !== first.coverage ||
      next.mission_id !== first.mission_id ||
      next.store_id !== first.store_id ||
      next.api_epoch !== first.api_epoch ||
      next.generation !== first.generation ||
      next.snapshot_token !== first.snapshot_token ||
      next.H !== first.H
    )
      throw new Error('Event snapshot changed');
    snapshot.events.push(...next.events);
    cursor = next.cursor;
  }
  return { ...snapshot, cursor: null, truncated: false };
}
export async function acknowledgeOperatorEvent(
  request: AckRequest,
  key: string,
  epoch: string
): Promise<AckReceipt> {
  return (
    await apiClient.post<AckReceipt>(`${base}/acknowledge`, request, {
      headers: { 'Idempotency-Key': key, 'X-Operator-Store-Epoch': epoch },
    })
  ).data;
}

function validatePage(page: EventSnapshot, missionId: string) {
  if (
    page.schema_version !== 1 ||
    page.mission_id !== missionId ||
    !Array.isArray(page.events) ||
    !Array.isArray(page.sources) ||
    page.truncated !== Boolean(page.cursor)
  )
    throw new Error('Incomplete or invalid event snapshot');
}
