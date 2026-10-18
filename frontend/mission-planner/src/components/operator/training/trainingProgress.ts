import {
  decodeRetryObservation,
  type RetryObservation,
} from './trainingRetryEvidence';
import { trainingSteps, type TrainingStageId } from './trainingSteps';

export interface TrainingIdentity {
  fixtureVersion: number;
  origin: string;
  storeId: string;
  epoch: string;
  missionId: string;
}
export interface ManualEvidence {
  outcomeId: string;
  observedAt: string;
  note: string;
}
export interface TrainingProgress extends TrainingIdentity {
  schemaVersion: 1;
  currentStage: TrainingStageId;
  visited: TrainingStageId[];
  skipped: TrainingStageId[];
  manualEvidence: ManualEvidence[];
  retryObservations?: RetryObservation[];
}
type Storage = Pick<globalThis.Storage, 'getItem' | 'setItem' | 'removeItem'>;
const fields = [
  'fixtureVersion',
  'origin',
  'storeId',
  'epoch',
  'missionId',
] as const;
const key = (identity: TrainingIdentity) =>
  `operator-training-progress:${JSON.stringify(fields.map((field) => identity[field]))}`;
const isStage = (value: unknown): value is TrainingStageId =>
  trainingSteps.some((step) => step.id === value);
const isObject = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === 'object' && !Array.isArray(value);
const validIdentity = (identity: TrainingIdentity) =>
  Number.isInteger(identity.fixtureVersion) &&
  identity.fixtureVersion > 0 &&
  fields
    .slice(1)
    .every(
      (field) =>
        typeof identity[field] === 'string' &&
        String(identity[field]).trim().length > 0
    );
function validProgress(
  value: unknown,
  identity: TrainingIdentity
): value is TrainingProgress {
  if (
    !isObject(value) ||
    !validIdentity(identity) ||
    value.schemaVersion !== 1 ||
    !fields.every((field) => value[field] === identity[field]) ||
    !isStage(value.currentStage)
  )
    return false;
  if (
    ![value.visited, value.skipped].every(
      (list) => Array.isArray(list) && list.every(isStage)
    )
  )
    return false;
  try {
    if (value.retryObservations !== undefined) {
      if (
        !Array.isArray(value.retryObservations) ||
        value.retryObservations.length > 20
      )
        return false;
      value.retryObservations.forEach((item) =>
        decodeRetryObservation(item, identity)
      );
    }
  } catch {
    return false;
  }
  return (
    Array.isArray(value.manualEvidence) &&
    value.manualEvidence.every(
      (item) =>
        isObject(item) &&
        typeof item.outcomeId === 'string' &&
        trainingSteps.some((step) =>
          (step.manual as readonly string[]).includes(item.outcomeId as string)
        ) &&
        typeof item.observedAt === 'string' &&
        Number.isFinite(Date.parse(item.observedAt)) &&
        typeof item.note === 'string' &&
        !!item.note.trim()
    )
  );
}
const message = (error: unknown) =>
  error instanceof Error ? error.message : String(error);
export function createProgress(identity: TrainingIdentity): TrainingProgress {
  if (!validIdentity(identity))
    throw new Error(
      'Training progress requires a complete private context identity.'
    );
  return {
    ...identity,
    schemaVersion: 1,
    currentStage: 'T01',
    visited: ['T01'],
    skipped: [],
    manualEvidence: [],
  };
}
export function moveProgress(
  progress: TrainingProgress,
  direction: 'next' | 'back' | 'skip'
): TrainingProgress {
  const index = trainingSteps.findIndex(
    (step) => step.id === progress.currentStage
  );
  const currentStage =
    trainingSteps[
      Math.max(
        0,
        Math.min(
          trainingSteps.length - 1,
          index + (direction === 'back' ? -1 : 1)
        )
      )
    ].id;
  return {
    ...progress,
    currentStage,
    visited: [...new Set([...progress.visited, currentStage])],
    skipped:
      direction === 'skip'
        ? [...new Set([...progress.skipped, progress.currentStage])]
        : [...progress.skipped],
    manualEvidence: progress.manualEvidence.map((item) => ({ ...item })),
  };
}
export function loadProgress(
  storage: Storage,
  identity: TrainingIdentity
): { progress: TrainingProgress | null; error: string | null } {
  try {
    if (!validIdentity(identity)) throw new Error('Invalid training identity.');
    const raw = storage.getItem(key(identity));
    if (raw === null) return { progress: null, error: null };
    const value: unknown = JSON.parse(raw);
    if (!validProgress(value, identity))
      throw new Error(
        'Stored guide progress has an invalid version, identity or lesson. It was retained for recovery.'
      );
    return { progress: value, error: null };
  } catch (error) {
    return { progress: null, error: message(error) };
  }
}
export function saveProgress(
  storage: Storage,
  progress: TrainingProgress
): { error: string | null } {
  try {
    if (!validProgress(progress, progress))
      throw new Error('Invalid guide progress.');
    storage.setItem(key(progress), JSON.stringify(progress));
    return { error: null };
  } catch (error) {
    return { error: message(error) };
  }
}
export function resetProgress(
  storage: Storage,
  identity: TrainingIdentity
): { error: string | null } {
  try {
    storage.removeItem(key(identity));
    return { error: null };
  } catch (error) {
    return { error: message(error) };
  }
}

export function revisitStage(
  progress: TrainingProgress,
  stage: TrainingStageId
): TrainingProgress {
  return {
    ...progress,
    currentStage: stage,
    visited: [...new Set([...progress.visited, stage])],
    skipped: progress.skipped.filter((id) => id !== stage),
    manualEvidence: progress.manualEvidence.map((item) => ({ ...item })),
  };
}
