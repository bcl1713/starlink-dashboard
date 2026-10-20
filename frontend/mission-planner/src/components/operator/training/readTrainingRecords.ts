import {
  getOperatorHealth,
  readOperatorHistory,
  readOperatorRecords,
} from '@/services/operator';
import type { RecordPage } from '@/types/operator';
import type { TrainingIdentity } from './trainingProgress';
import { collectRecordEvidence } from './trainingEvidence';

async function allPages(
  read: (cursor?: string) => Promise<RecordPage>,
  expectedH?: number
) {
  const items: RecordPage['items'] = [];
  const cursors = new Set<string>();
  let cursor: string | undefined;
  let H = expectedH;
  do {
    const page = await read(cursor);
    if (H !== undefined && page.H !== H)
      throw new Error('Journal changed during evidence checking; check again.');
    H = page.H;
    items.push(...page.items);
    cursor = page.cursor ?? undefined;
    if (cursor && (cursors.has(cursor) || cursors.size >= 100))
      throw new Error(
        'Journal pagination did not finish; evidence remains incomplete.'
      );
    if (cursor) cursors.add(cursor);
  } while (cursor);
  return { items, H };
}
/** Explicit user check only. No polling, learner commands or receipt replay. */
export async function readTrainingRecords(
  identity: TrainingIdentity,
  namespace: string,
  prerequisiteIds: readonly string[]
) {
  const current = await allPages((cursor) =>
    readOperatorRecords(
      { mission_id: identity.missionId, include_removed: true },
      cursor
    )
  );
  const history: RecordPage['items'] = [];
  for (const item of current.items) {
    if (
      prerequisiteIds.includes(item.record.record_id) &&
      item.record.version === 1
    )
      continue;
    const versions = await allPages(
      (cursor) => readOperatorHistory(item.record.record_id, cursor),
      current.H
    );
    history.push(...versions.items);
  }
  const health = await getOperatorHealth();
  if (
    !health.ready ||
    health.store_id !== identity.storeId ||
    health.api_epoch !== identity.epoch ||
    health.source_mode !== 'simulation' ||
    health.simulation_run_id !== namespace
  )
    throw new Error(
      'Training store changed during checking; reopen the current private mission.'
    );
  return {
    H: current.H,
    evidenceRecords: [...current.items, ...history].map((item) => item.record),
    ...collectRecordEvidence({
      missionId: identity.missionId,
      ready: true,
      complete: true,
      historyComplete: true,
      fresh: true,
      records: current.items.map((item) => item.record),
      history: history.map((item) => item.record),
      prerequisiteIds,
      receipts: [],
    }),
  };
}
