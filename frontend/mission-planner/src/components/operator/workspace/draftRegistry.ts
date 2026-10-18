import { createClientId } from '@/lib/clientId';
import type { OperatorInput, SavedRecord } from '@/types/operator';
import type { DraftEnvelope, DraftTarget, PersistenceResult } from './types';

export const draftPrefix = 'operator-workspace-draft:v1:';
const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T;
const durable = (): PersistenceResult => ({ state: 'durable', message: null });
const memoryOnly = (message: string): PersistenceResult => ({
  state: 'memory_only',
  message,
});
const scopes = ['mission', 'preflight', 'leg', 'between_legs', 'postflight'];
const types = [
  'journal_entry',
  'call',
  'conference',
  'participation',
  'issue',
  'transport_decision',
];
const nullableString = (value: unknown) =>
  value === null || typeof value === 'string';

export function isDraftTarget(value: unknown): value is DraftTarget {
  if (!value || typeof value !== 'object') return false;
  const target = value as DraftTarget;
  return (
    ['storeId', 'epoch', 'missionId'].every(
      (key) =>
        typeof target[key as keyof DraftTarget] === 'string' &&
        String(target[key as keyof DraftTarget]).length > 0
    ) &&
    types.includes(target.recordType) &&
    scopes.includes(target.scope) &&
    (target.sourceMode === 'live'
      ? target.simulationRunId === null
      : target.sourceMode === 'simulation' &&
        typeof target.simulationRunId === 'string' &&
        target.simulationRunId.length > 0) &&
    nullableString(target.recordId) &&
    nullableString(target.newDraftId) &&
    nullableString(target.legId) &&
    nullableString(target.previousLegId) &&
    nullableString(target.nextLegId) &&
    (target.correctionVersion === null ||
      (Number.isInteger(target.correctionVersion) &&
        target.correctionVersion > 0))
  );
}

export function isOperatorInput(value: unknown): value is OperatorInput {
  if (!value || typeof value !== 'object') return false;
  const row = value as Record<string, unknown>;
  const payload = row.payload as Record<string, unknown> | undefined;
  const time = row.time as Record<string, unknown> | undefined;
  return (
    row.schema_version === 1 &&
    typeof row.mission_id === 'string' &&
    types.includes(String(row.record_type)) &&
    scopes.includes(String(row.scope)) &&
    nullableString(row.leg_id) &&
    !!payload &&
    payload.schema_version === 1 &&
    typeof payload.entry_type === 'string' &&
    typeof payload.title === 'string' &&
    typeof payload.note === 'string' &&
    nullableString(payload.previous_leg_id) &&
    nullableString(payload.next_leg_id) &&
    !!time &&
    ['exact', 'approximate', 'unknown'].includes(String(time.precision)) &&
    ['instant', 'ongoing', 'known', 'unknown'].includes(
      String(time.end_state)
    ) &&
    ['occurred_at', 'ended_at', 'planned_start_at', 'planned_end_at'].every(
      (key) => nullableString(time[key])
    )
  );
}

function validEnvelope(value: unknown, key: string): value is DraftEnvelope {
  if (!value || typeof value !== 'object') return false;
  const row = value as DraftEnvelope;
  const t = row.target;
  return (
    row.schemaVersion === 1 &&
    typeof row.draftId === 'string' &&
    key === draftPrefix + row.draftId &&
    Number.isInteger(row.revision) &&
    row.revision > 0 &&
    isDraftTarget(t) &&
    (row.baseVersion === null ||
      (Number.isInteger(row.baseVersion) && row.baseVersion > 0)) &&
    (t.recordId !== null
      ? t.newDraftId === null
      : t.newDraftId === row.draftId) &&
    isOperatorInput(row.input) &&
    matches(t, row.input)
  );
}

function matches(target: DraftTarget, input: OperatorInput) {
  return (
    target.missionId === input.mission_id &&
    target.recordType === input.record_type &&
    target.scope === input.scope &&
    target.legId === input.leg_id &&
    target.previousLegId === input.payload.previous_leg_id &&
    target.nextLegId === input.payload.next_leg_id
  );
}

/** Tab-local input ownership. This registry never dispatches or retries commands. */
export class DraftRegistry {
  private drafts = new Map<string, DraftEnvelope>();
  private errors: { key: string; message: string }[] = [];
  private storage: Storage | null;
  constructor(storage: Storage | null) {
    this.storage = storage;
    if (!storage) return;
    try {
      for (let i = 0; i < storage.length; i++) {
        const key = storage.key(i);
        if (!key?.startsWith(draftPrefix)) continue;
        try {
          const value: unknown = JSON.parse(storage.getItem(key)!);
          if (!validEnvelope(value, key)) throw new Error('Invalid envelope');
          this.drafts.set(value.draftId, { ...value, persistence: durable() });
        } catch {
          this.errors.push({
            key,
            message:
              'Stored draft is invalid. It remains available for recovery.',
          });
        }
      }
    } catch {
      this.errors.push({
        key: draftPrefix,
        message: 'Draft storage unavailable. Keep this tab open.',
      });
    }
  }

  createDraft(
    target: DraftTarget,
    input: OperatorInput,
    baseRecord: SavedRecord | null = null
  ): DraftEnvelope {
    if (!matches(target, input))
      throw new Error('Draft input does not match its pinned target.');
    if (
      baseRecord &&
      (baseRecord.record_id !== target.recordId ||
        baseRecord.record_type !== target.recordType ||
        !Number.isInteger(baseRecord.version) ||
        baseRecord.version < 1)
    )
      throw new Error('Saved base does not match the draft record target.');
    const draftId = createClientId();
    return this.parkDraft({
      schemaVersion: 1,
      draftId,
      target: { ...target, newDraftId: target.recordId ? null : draftId },
      input,
      baseRecord,
      baseVersion: baseRecord?.version ?? null,
      revision: 1,
      persistence: durable(),
    });
  }

  parkDraft(envelope: DraftEnvelope): DraftEnvelope {
    if (!validEnvelope(envelope, draftPrefix + envelope.draftId))
      throw new Error('Invalid draft envelope.');
    const previous = this.drafts.get(envelope.draftId);
    if (previous && envelope.revision < previous.revision)
      return clone(previous);
    const retained = clone(envelope);
    retained.persistence = durable();
    this.drafts.set(retained.draftId, retained);
    try {
      if (!this.storage) throw new Error('Unavailable');
      this.storage.setItem(
        draftPrefix + retained.draftId,
        JSON.stringify(retained)
      );
    } catch {
      retained.persistence = memoryOnly(
        'Draft could not be retained across reload. Keep this tab open.'
      );
    }
    return clone(retained);
  }

  resumeDraft(draftId: string): DraftEnvelope | null {
    const value = this.drafts.get(draftId);
    return value ? clone(value) : null;
  }

  editDraft(draftId: string, input: OperatorInput): DraftEnvelope | null {
    const current = this.resumeDraft(draftId);
    if (!current) return null;
    return this.parkDraft({
      ...current,
      input,
      revision: current.revision + 1,
    });
  }

  discardDraft(draftId: string): PersistenceResult {
    try {
      if (!this.storage) throw new Error('Unavailable');
      this.storage.removeItem(draftPrefix + draftId);
      this.drafts.delete(draftId);
      return durable();
    } catch {
      const result = memoryOnly(
        'Stored draft could not be cleared. Keep this tab open.'
      );
      const draft = this.drafts.get(draftId);
      if (draft) draft.persistence = result;
      return result;
    }
  }

  retireSubmitted(
    draftId: string,
    submittedRevision: number
  ): PersistenceResult {
    const current = this.drafts.get(draftId);
    return current?.revision === submittedRevision
      ? this.discardDraft(draftId)
      : durable();
  }

  listDrafts(): DraftEnvelope[] {
    return [...this.drafts.values()].map(clone);
  }
  recoveryErrors() {
    return clone(this.errors);
  }
}

let defaultRegistry: DraftRegistry | undefined;
export function getDraftRegistry() {
  if (!defaultRegistry) {
    let storage: Storage | null = null;
    try {
      storage = sessionStorage;
    } catch {
      /* In-memory ownership remains available. */
    }
    defaultRegistry = new DraftRegistry(storage);
  }
  return defaultRegistry;
}
export const createDraft = (target: DraftTarget, input: OperatorInput) =>
  getDraftRegistry().createDraft(target, input);
export const parkDraft = (draft: DraftEnvelope) =>
  getDraftRegistry().parkDraft(draft);
export const resumeDraft = (draftId: string) =>
  getDraftRegistry().resumeDraft(draftId);
export const discardDraft = (draftId: string) =>
  getDraftRegistry().discardDraft(draftId);
