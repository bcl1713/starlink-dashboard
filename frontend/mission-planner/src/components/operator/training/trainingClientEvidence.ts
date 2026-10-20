import { sameInputValue } from './trainingRetryReceipt';
import type { SavedRecord } from '@/types/operator';
import type { DraftEnvelope } from '../workspace/types';
import { draftPrefix, isDraftEnvelope } from '../workspace/draftRegistry';
import type { TrainingIdentity } from './trainingProgress';
import { sameJson } from './trainingRecordIdentity';

export interface ClientObservation {
  identity: TrainingIdentity;
  namespace: string;
  observedAt: number;
  journalH: number;
  online: boolean;
  drafts: DraftEnvelope[];
}
function matches(
  draft: DraftEnvelope,
  identity: TrainingIdentity,
  namespace: string
) {
  const t = draft.target;
  return (
    t.storeId === identity.storeId &&
    t.epoch === identity.epoch &&
    t.missionId === identity.missionId &&
    t.sourceMode === 'simulation' &&
    t.simulationRunId === namespace
  );
}
/** Raw browser/registry reads, never commands or saved completion booleans. */
export function decodeClientObservation(
  value: unknown,
  identity: TrainingIdentity,
  namespace?: string
): ClientObservation {
  if (!value || typeof value !== 'object')
    throw new Error('Invalid browser observation');
  const raw = value as ClientObservation;
  if (
    !sameJson(raw.identity, identity) ||
    !/^operator-training-v1-[0-9a-f-]{36}$/.test(raw.namespace) ||
    (namespace !== undefined && raw.namespace !== namespace) ||
    !Number.isSafeInteger(raw.observedAt) ||
    raw.observedAt <= 0 ||
    !Number.isSafeInteger(raw.journalH) ||
    raw.journalH < 0 ||
    typeof raw.online !== 'boolean' ||
    !Array.isArray(raw.drafts) ||
    raw.drafts.length > 20 ||
    new Set(raw.drafts.map((draft) => draft?.draftId)).size !==
      raw.drafts.length ||
    !raw.drafts.every(
      (draft) =>
        isDraftEnvelope(draft, draftPrefix + draft?.draftId) &&
        matches(draft, identity, raw.namespace) &&
        ['durable', 'memory_only'].includes(draft.persistence?.state) &&
        (draft.persistence.state === 'durable'
          ? draft.persistence.message === null
          : typeof draft.persistence.message === 'string' &&
            !!draft.persistence.message.trim())
    )
  )
    throw new Error('Browser observation does not match this private mission');
  return JSON.parse(JSON.stringify(raw)) as ClientObservation;
}
export function retainClientObservation(
  identity: TrainingIdentity,
  namespace: string,
  journalH: number,
  online: boolean,
  drafts: readonly DraftEnvelope[],
  previous: readonly ClientObservation[],
  now = Date.now(),
  records: readonly SavedRecord[] = []
): ClientObservation[] {
  const reads: ClientObservation[] = [];
  for (const raw of previous.slice(-8)) {
    try {
      reads.push(decodeClientObservation(raw, identity, namespace));
    } catch {
      /* Foreign reads are not evidence. */
    }
  }
  try {
    const next = decodeClientObservation(
      {
        identity,
        namespace,
        observedAt: now,
        journalH,
        online,
        drafts: drafts.filter((draft) => matches(draft, identity, namespace)),
      },
      identity,
      namespace
    );
    const last = reads.at(-1);
    if (
      !last ||
      last.online !== next.online ||
      last.journalH !== next.journalH ||
      !sameJson(last.drafts, next.drafts)
    )
      reads.push(next);
  } catch {
    /* Missing or oversized reads leave the exercise incomplete. */
  }
  // Keep the raw pair for each already-provable recovery, plus recent reads.
  // Saved rows choose retention only; every outcome still needs a fresh backend
  // comparison in collectClientEvidence, including after a reload.
  const pinned = new Set<ClientObservation>();
  const proven = new Set<string>();
  const eligible = reads.filter(
    (read) => read.observedAt <= now && read.journalH <= journalH
  );
  for (const before of eligible)
    for (const after of eligible) {
      for (const outcome of pairOutcomes(
        identity,
        journalH,
        records,
        before,
        after
      )) {
        if (proven.has(outcome)) continue;
        proven.add(outcome);
        pinned.add(before);
        pinned.add(after);
      }
    }
  const recent = reads
    .filter((read) => !pinned.has(read))
    .slice(-(8 - pinned.size));
  const selected = new Set([...pinned, ...recent]);
  return reads.filter((read) => selected.has(read));
}
function retained(before: DraftEnvelope, after: DraftEnvelope) {
  return (
    before.draftId === after.draftId &&
    after.revision >= before.revision &&
    sameJson(before.target, after.target) &&
    sameJson(before.input, after.input)
  );
}
function differentScope(a: DraftEnvelope, b: DraftEnvelope) {
  return ['scope', 'legId', 'previousLegId', 'nextLegId'].some(
    (key) =>
      a.target[key as keyof typeof a.target] !==
      b.target[key as keyof typeof b.target]
  );
}
export function collectClientEvidence(
  identity: TrainingIdentity,
  namespace: string,
  H: number,
  records: readonly SavedRecord[],
  values: unknown,
  now = Date.now()
): string[] {
  if (
    !Array.isArray(values) ||
    values.length > 8 ||
    !Number.isSafeInteger(H) ||
    H < 0
  )
    return [];
  const reads: ClientObservation[] = [];
  for (const value of values) {
    try {
      const read = decodeClientObservation(value, identity, namespace);
      if (read.observedAt <= now && read.journalH <= H) reads.push(read);
    } catch {
      /* Corrupt, foreign or generic progress flags cannot prove recovery. */
    }
  }
  const outcomes = new Set<string>();
  for (const before of reads)
    for (const after of reads)
      for (const outcome of pairOutcomes(identity, H, records, before, after))
        outcomes.add(outcome);
  return [...outcomes];
}
function pairOutcomes(
  identity: TrainingIdentity,
  H: number,
  records: readonly SavedRecord[],
  before: ClientObservation,
  after: ClientObservation
): string[] {
  if (after.observedAt <= before.observedAt || after.journalH < before.journalH)
    return [];
  const outcomes = new Set<string>();
  for (const draft of before.drafts) {
    const kept = after.drafts.find((candidate) => retained(draft, candidate));
    if (!kept) continue;
    if (
      after.drafts.some(
        (other) =>
          other.draftId !== draft.draftId &&
          !before.drafts.some((prior) => prior.draftId === other.draftId) &&
          differentScope(draft, other)
      )
    )
      outcomes.add('draft-switch-retained');
    const saved = records.some(
      (row) =>
        row.mission_id === identity.missionId &&
        row.provenance.source_mode === 'simulation' &&
        !row.deleted &&
        row.journal_seq > before.journalH &&
        row.journal_seq <= H &&
        (draft.target.recordId
          ? row.record_id === draft.target.recordId &&
            row.version > (draft.baseVersion ?? 0)
          : row.version === 1 && row.operation === 'create') &&
        row.record_type === draft.input.record_type &&
        row.scope === draft.input.scope &&
        row.leg_id === draft.input.leg_id &&
        sameInputValue(draft.input.time, row.time) &&
        sameInputValue(draft.input.payload, row.payload)
    );
    if (saved && !before.online && after.online)
      outcomes.add('offline-draft-retained');
    if (
      saved &&
      draft.persistence.state === 'memory_only' &&
      kept.persistence.state === 'durable'
    )
      outcomes.add('storage-unavailable-recovery');
  }
  return [...outcomes];
}
