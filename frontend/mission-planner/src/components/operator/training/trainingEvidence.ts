import type { CommandReceipt, SavedRecord } from '@/types/operator';
import type { TrainingEvidence } from './trainingSteps';
import { lifecycleOutcomes } from './trainingLifecycleEvidence';
import { sameRecord } from './trainingRecordIdentity';

export interface RecordEvidenceSource {
  missionId: string;
  ready: boolean;
  complete: boolean;
  historyComplete: boolean;
  fresh: boolean;
  records: readonly SavedRecord[];
  history: readonly SavedRecord[];
  prerequisiteIds: readonly string[];
  receipts: readonly CommandReceipt[];
}
/** Pure adapter over ordinary journal responses. It performs no writes or reads. */
export function collectRecordEvidence(
  source: RecordEvidenceSource
): TrainingEvidence {
  const outcomes = new Set<string>();
  const eligible = (r: SavedRecord) =>
    r.mission_id === source.missionId &&
    r.provenance.source_mode === 'simulation';
  const receipted = (record: SavedRecord) =>
    (source.historyComplete &&
      source.history.some((saved) => sameRecord(saved, record))) ||
    source.receipts.some(
      (receipt) =>
        receipt.command_id === record.command_id &&
        receipt.saved_records.some((saved) => sameRecord(saved, record))
    );
  const records = source.records.filter(
    (r) =>
      eligible(r) &&
      !r.deleted &&
      (!source.prerequisiteIds.includes(r.record_id) || r.version > 1) &&
      receipted(r)
  );
  const history = source.history.filter((r) => eligible(r) && receipted(r));
  const consistent = !source.records.some((record) =>
    history.some(
      (saved) =>
        saved.record_id === record.record_id &&
        saved.version === record.version &&
        !sameRecord(saved, record)
    )
  );
  for (const r of records) {
    const p = r.payload;
    const versions = [
      ...history.filter(
        (v) => v.record_id === r.record_id && v.version !== r.version
      ),
      r,
    ].sort((a, b) => a.version - b.version);
    if (r.record_type === 'journal_entry' && p.entry_type === 'note') {
      outcomes.add('scoped-note');
      if (
        r.scope === 'between_legs' &&
        p.previous_leg_id &&
        p.next_leg_id &&
        p.previous_leg_id !== p.next_leg_id
      )
        outcomes.add('between-legs-note');
    }
    if (p.entry_type === 'call') {
      if (!source.prerequisiteIds.includes(r.record_id))
        outcomes.add('call-created');
      if (p.status === 'completed') outcomes.add('call-completed');
      if (
        p.status === 'completed' &&
        (!r.time.occurred_at ||
          !r.time.ended_at ||
          r.time.precision === 'unknown')
      )
        outcomes.add('call-unknown-time');
      if (p.prep_lead_minutes === 0) outcomes.add('call-prep-zero');
      if (
        versions.some(
          (v) =>
            v.time.planned_start_at &&
            r.time.planned_start_at &&
            v.time.planned_start_at !== r.time.planned_start_at
        )
      )
        outcomes.add('call-rescheduled');
      if (
        versions.some(
          (v) =>
            v.payload.entry_type === 'call' && v.payload.status === 'cancelled'
        ) &&
        p.status !== 'cancelled'
      )
        outcomes.add('call-cancelled-reinstated');
      if (
        source.historyComplete &&
        versions.some(
          (restored) =>
            restored.operation === 'restore' &&
            !restored.deleted &&
            versions.some(
              (removed) =>
                removed.operation === 'remove' &&
                removed.deleted &&
                restored.previous_version === removed.version
            )
        )
      )
        outcomes.add('call-removed-restored');
      if (
        source.historyComplete &&
        versions.length > 1 &&
        versions[0].version === 1 &&
        versions[versions.length - 1].version === r.version &&
        versions.every(
          (v, index) =>
            index === 0 || v.previous_version === versions[index - 1].version
        )
      )
        outcomes.add('call-history');
    }
    if (
      p.entry_type === 'capability_assessment' &&
      versions.some(
        (row) =>
          row.payload.entry_type === 'capability_assessment' &&
          ((row.payload.functional_status !== 'unknown' &&
            row.payload.redundancy_status === 'unknown') ||
            (row.payload.functional_status === 'unknown' &&
              row.payload.redundancy_status !== 'unknown'))
      )
    )
      outcomes.add('capability-independent');
    if (p.entry_type === 'issue') {
      const statuses = versions.flatMap((v) =>
        v.payload.entry_type === 'issue' ? [v.payload.status] : []
      );
      const monitoring = statuses.indexOf('monitoring');
      const resolved = statuses.indexOf('resolved', monitoring + 1);
      if (
        monitoring >= 0 &&
        resolved > monitoring &&
        statuses.indexOf('reopened', resolved + 1) > resolved
      )
        outcomes.add('issue-monitor-resolve-reopen');
      if (
        versions.some(
          (candidate, index) =>
            candidate.payload.entry_type === 'issue' &&
            !candidate.payload.follow_up_at &&
            versions
              .slice(0, index)
              .some(
                (prior) =>
                  prior.payload.entry_type === 'issue' &&
                  prior.payload.follow_up_at
              )
        )
      )
        outcomes.add('issue-followup-cleared');
      if (
        versions.some((candidate) => {
          const corrected = candidate.payload;
          const prior = versions.find(
            (row) => row.version === candidate.previous_version
          )?.payload;
          return (
            corrected.entry_type === 'issue' &&
            corrected.corrects_version &&
            versions.some(
              (row) =>
                row.version === corrected.corrects_version &&
                row.version < candidate.version
            ) &&
            prior?.entry_type === 'issue' &&
            corrected.status === prior.status &&
            corrected.mitigation === prior.mitigation &&
            corrected.follow_up_at === prior.follow_up_at
          );
        })
      )
        outcomes.add('issue-historical-correction');
    }
  }
  for (const outcome of lifecycleOutcomes(
    records,
    history,
    source.historyComplete
  ))
    outcomes.add(outcome);
  return {
    available: source.ready && source.complete && consistent,
    fresh: source.fresh,
    outcomes: [...outcomes],
  };
}

export interface CheckedTrainingEvidence extends TrainingEvidence {
  identity: string;
  H: number | undefined;
  checkedAt: number;
  eventGeneration?: string;
}
export function isCurrentTrainingEvidence(
  checked: CheckedTrainingEvidence | null,
  identity: string | undefined,
  H: number | undefined,
  now: number,
  eventGeneration?: string
): checked is CheckedTrainingEvidence {
  return (
    !!checked &&
    checked.available &&
    checked.fresh &&
    !!identity &&
    checked.identity === identity &&
    H !== undefined &&
    checked.H === H &&
    (checked.eventGeneration === undefined ||
      checked.eventGeneration === eventGeneration) &&
    now >= checked.checkedAt &&
    now - checked.checkedAt < 30_000
  );
}
