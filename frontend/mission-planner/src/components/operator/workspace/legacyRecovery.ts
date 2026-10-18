import { DraftRegistry, isOperatorInput } from './draftRegistry';
import type { DraftTarget, RecoveryResult } from './types';
import type { OperatorInput } from '@/types/operator';
import { issueDraftPrefix as issuePrefix } from '@/hooks/api/useOperatorIssueDraft';
import { transportDraftPrefix as transportPrefix } from '@/hooks/api/useOperatorTransportDraft';

type LegacyIdentity = Pick<
  DraftTarget,
  'storeId' | 'epoch' | 'sourceMode' | 'simulationRunId' | 'missionId'
> & { recordId: string };

function canonical(value: unknown): string {
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  if (value && typeof value === 'object')
    return (
      '{' +
      Object.entries(value)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([k, v]) => JSON.stringify(k) + ':' + canonical(v))
        .join(',') +
      '}'
    );
  return JSON.stringify(value);
}

/** Decode legacy storage formats; never infer a pending command as unsent input. */
export function legacyDraftTarget(
  key: string,
  input: OperatorInput,
  identity: string
): DraftTarget | null {
  const context: unknown = JSON.parse(identity);
  if (!Array.isArray(context) || context.length !== 4) return null;
  const [storeId, epoch, sourceMode, simulationRunId] = context;
  if (
    typeof storeId !== 'string' ||
    typeof epoch !== 'string' ||
    !['live', 'simulation'].includes(sourceMode) ||
    !(simulationRunId === null || typeof simulationRunId === 'string')
  )
    return null;
  let recordId: string;
  if (key.startsWith(issuePrefix)) {
    const legacy = JSON.parse(key.slice(issuePrefix.length)) as LegacyIdentity;
    if (
      legacy.storeId !== storeId ||
      legacy.epoch !== epoch ||
      legacy.sourceMode !== sourceMode ||
      legacy.simulationRunId !== simulationRunId ||
      legacy.missionId !== input.mission_id ||
      typeof legacy.recordId !== 'string'
    )
      return null;
    recordId = legacy.recordId;
  } else {
    const prefix = `${transportPrefix}${identity}:${input.mission_id}:`;
    if (!key.startsWith(prefix) || input.record_type !== 'transport_decision')
      return null;
    recordId = key.slice(prefix.length);
  }
  const correction = /^(.*):correction:([1-9]\d*)$/.exec(recordId);
  return {
    storeId,
    epoch,
    sourceMode,
    simulationRunId,
    missionId: input.mission_id,
    recordType: input.record_type,
    recordId: ['new', 'new-issue', 'new-capability'].includes(recordId)
      ? null
      : (correction?.[1] ?? recordId),
    newDraftId: null,
    scope: input.scope,
    legId: input.leg_id,
    previousLegId: input.payload.previous_leg_id,
    nextLegId: input.payload.next_leg_id,
    correctionVersion: correction ? Number(correction[2]) : null,
  };
}

export function recoverLegacyDrafts(
  storage: Storage,
  identity: string,
  registry = new DraftRegistry(storage)
): RecoveryResult {
  const result: RecoveryResult = {
    migratedDraftIds: [],
    quarantinedKeys: [],
    errors: [],
  };
  let keys: string[];
  try {
    keys = Array.from({ length: storage.length }, (_, i) =>
      storage.key(i)
    ).filter((key): key is string => key !== null);
  } catch {
    return {
      ...result,
      errors: [
        {
          key: 'legacy-storage',
          message: 'Draft storage unavailable. Keep this tab open.',
        },
      ],
    };
  }
  for (const key of keys) {
    if (key.startsWith('operator-367-pending:')) {
      result.quarantinedKeys.push(key);
      continue;
    }
    if (!key.startsWith(issuePrefix) && !key.startsWith(transportPrefix))
      continue;
    try {
      const value = JSON.parse(storage.getItem(key)!) as Record<
        string,
        unknown
      >;
      if (!isOperatorInput(value.input)) {
        result.quarantinedKeys.push(key);
        continue;
      }
      const target = legacyDraftTarget(key, value.input, identity);
      if (!target) {
        result.quarantinedKeys.push(key);
        continue;
      }
      const { input, baseVersion, version, ...editorState } = value;
      const base = baseVersion ?? version ?? null;
      if (base !== null && (!Number.isInteger(base) || Number(base) < 1)) {
        result.quarantinedKeys.push(key);
        continue;
      }
      const fingerprint = canonical({ target, input, base, editorState });
      let envelope = registry
        .listDrafts()
        .find(
          (d) => d.legacyKey === key || d.legacyFingerprint === fingerprint
        );
      if (!envelope) envelope = registry.createDraft(target, value.input);
      envelope = registry.parkDraft({
        ...envelope,
        baseVersion: base as number | null,
        editorState,
        legacyKey: key,
        legacyFingerprint: fingerprint,
      });
      if (envelope.persistence.state !== 'durable') {
        result.errors.push({ key, message: envelope.persistence.message! });
        continue;
      }
      // Retire only after the complete replacement has been durably written.
      storage.removeItem(key);
      if (!result.migratedDraftIds.includes(envelope.draftId))
        result.migratedDraftIds.push(envelope.draftId);
    } catch {
      result.quarantinedKeys.push(key);
      result.errors.push({
        key,
        message:
          'Legacy draft could not be migrated or cleared. Original data remains available for recovery.',
      });
    }
  }
  return result;
}
