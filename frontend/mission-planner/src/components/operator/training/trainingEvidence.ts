import type { CommandReceipt, SavedRecord } from '@/types/operator';
import type { TrainingEvidence } from './trainingSteps';

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
    r.provenance.source_mode === 'simulation' &&
    !source.prerequisiteIds.includes(r.record_id);
  const receipted = (r: SavedRecord) =>
    (source.historyComplete &&
      source.history.some(
        (saved) =>
          saved.record_id === r.record_id &&
          saved.version === r.version &&
          saved.command_id === r.command_id &&
          saved.mission_id === r.mission_id &&
          saved.record_type === r.record_type &&
          saved.deleted === r.deleted &&
          JSON.stringify(saved.payload) === JSON.stringify(r.payload) &&
          JSON.stringify(saved.time) === JSON.stringify(r.time)
      )) ||
    source.receipts.some(
      (receipt) =>
        receipt.command_id === r.command_id &&
        receipt.saved_records.some(
          (saved) =>
            saved.record_id === r.record_id &&
            saved.version === r.version &&
            saved.command_id === r.command_id &&
            saved.mission_id === r.mission_id
        )
    );
  const records = source.records.filter(
    (r) => eligible(r) && !r.deleted && receipted(r)
  );
  const history = source.history.filter((r) => eligible(r) && receipted(r));
  for (const r of records) {
    const p = r.payload;
    const versions = history
      .filter((v) => v.record_id === r.record_id)
      .sort((a, b) => a.version - b.version);
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
      outcomes.add('call-created');
      if (p.status === 'completed' && r.time.occurred_at && r.time.ended_at)
        outcomes.add('call-completed');
      if (!r.time.occurred_at && r.time.precision === 'unknown')
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
        r.operation === 'restore' &&
        versions.some((v) => v.deleted && v.operation === 'remove')
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
    if (p.entry_type === 'participation') {
      if (
        p.state === 'left' &&
        r.time.occurred_at &&
        r.time.ended_at &&
        Date.parse(r.time.ended_at) >= Date.parse(r.time.occurred_at)
      )
        outcomes.add('participation-joined-left');
      const prior = records.find(
        (v) => v.record_id === p.resumes_participation_id
      );
      if (
        prior &&
        prior.record_id !== r.record_id &&
        prior.payload.entry_type === 'participation' &&
        (prior.payload.state === 'left' ||
          prior.payload.state === 'interrupted') &&
        prior.time.occurred_at &&
        prior.time.ended_at &&
        r.time.occurred_at &&
        Date.parse(r.time.occurred_at) >= Date.parse(prior.time.ended_at) &&
        prior.payload.call_id === p.call_id &&
        prior.payload.conference_id === p.conference_id &&
        prior.payload.participant === p.participant
      )
        outcomes.add('participation-resumed-new-interval');
    }
    if (p.entry_type === 'conference') {
      if (p.status === 'established' && p.verified_at)
        outcomes.add('conference-established-verified');
      if (
        p.status === 'established' &&
        versions.some(
          (v) =>
            v.payload.entry_type === 'conference' &&
            v.payload.status === 'interrupted'
        )
      )
        outcomes.add('conference-interrupted-restored');
    }
    if (p.entry_type === 'transport_decision') {
      if (
        p.services.some(
          (row) =>
            row.applied && !row.intended && !row.requested && !row.checked
        )
      )
        outcomes.add('applied-only-report');
      if (
        p.services.filter((row) => row.checked?.time.at).length >= 2 &&
        new Set(
          p.services
            .filter((row) => row.checked?.time.at)
            .map((row) => row.service)
        ).size >= 2
      )
        outcomes.add('independent-service-checks');
    }
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
        !p.follow_up_at &&
        versions.some(
          (v) => v.payload.entry_type === 'issue' && v.payload.follow_up_at
        )
      )
        outcomes.add('issue-followup-cleared');
      if (
        p.corrects_version &&
        versions.some(
          (v) => v.version === p.corrects_version && v.version < r.version
        )
      )
        outcomes.add('issue-historical-correction');
    }
  }
  return {
    available: source.ready && source.complete,
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
