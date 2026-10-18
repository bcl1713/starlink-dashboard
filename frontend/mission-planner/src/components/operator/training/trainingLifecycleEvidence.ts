import type { SavedRecord } from '@/types/operator';
import { sameJson } from './trainingRecordIdentity';

/** Receipted or authoritative same-mission simulation rows, supplied by the adapter. */
export function lifecycleOutcomes(
  records: readonly SavedRecord[],
  history: readonly SavedRecord[],
  historyComplete: boolean
): string[] {
  const outcomes = new Set<string>();
  const connected = new Set<string>();
  if (
    records.filter(
      (row) =>
        row.payload.entry_type === 'participation' &&
        row.payload.state === 'connected'
    ).length >= 2
  )
    outcomes.add('participation-overlap');
  for (const row of (historyComplete ? [...history] : []).sort(
    (a, b) => a.journal_seq - b.journal_seq
  )) {
    if (row.payload.entry_type !== 'participation') continue;
    if (!row.deleted && row.payload.state === 'connected')
      connected.add(row.record_id);
    else connected.delete(row.record_id);
    if (connected.size >= 2) outcomes.add('participation-overlap');
  }
  for (const record of records) {
    const payload = record.payload;
    const versions = [
      ...history.filter(
        (row) =>
          row.record_id === record.record_id && row.version !== record.version
      ),
      record,
    ].sort((a, b) => a.version - b.version);
    if (payload.entry_type === 'participation') {
      const knownInterval =
        record.time.occurred_at &&
        record.time.ended_at &&
        Date.parse(record.time.ended_at) >= Date.parse(record.time.occurred_at);
      if (
        payload.state === 'left' &&
        (knownInterval ||
          versions.some(
            (row) =>
              row.payload.entry_type === 'participation' &&
              row.payload.state === 'connected'
          ))
      )
        outcomes.add('participation-joined-left');
      const prior = records.find(
        (row) => row.record_id === payload.resumes_participation_id
      );
      if (
        prior &&
        prior.record_id !== record.record_id &&
        prior.payload.entry_type === 'participation' &&
        ['left', 'interrupted'].includes(prior.payload.state ?? '') &&
        (!prior.time.ended_at ||
          !record.time.occurred_at ||
          Date.parse(record.time.occurred_at) >=
            Date.parse(prior.time.ended_at)) &&
        prior.payload.call_id === payload.call_id &&
        prior.payload.conference_id === payload.conference_id &&
        prior.payload.participant === payload.participant
      )
        outcomes.add('participation-resumed-new-interval');
    }
    if (payload.entry_type === 'conference') {
      if (
        versions.some(
          (row) =>
            row.payload.entry_type === 'conference' &&
            row.payload.status === 'established' &&
            row.payload.verified_at
        )
      )
        outcomes.add('conference-established-verified');
      const interrupted = versions.findIndex(
        (row) =>
          row.payload.entry_type === 'conference' &&
          row.payload.status === 'interrupted'
      );
      if (
        interrupted >= 0 &&
        versions
          .slice(interrupted + 1)
          .some(
            (row) =>
              row.payload.entry_type === 'conference' &&
              row.payload.status === 'established'
          )
      )
        outcomes.add('conference-interrupted-restored');
      const linked = records.filter(
        (row) =>
          row.payload.entry_type === 'call' &&
          row.payload.conference_id === record.record_id
      );
      if (
        versions.some(
          (row) =>
            row.payload.entry_type === 'conference' &&
            row.payload.status === 'closed'
        ) &&
        new Set(linked.map((row) => row.record_id)).size >= 2
      )
        outcomes.add('conference-reused-closed');
    }
    if (payload.entry_type === 'transport_decision') {
      if (
        versions.some(
          (row) =>
            row.payload.entry_type === 'transport_decision' &&
            row.payload.services.some(
              (service) =>
                service.applied &&
                !service.intended &&
                !service.requested &&
                !service.checked
            )
        )
      )
        outcomes.add('applied-only-report');
      const checked = payload.services.filter(
        (row) => row.checked && row.checked.result !== 'unknown'
      );
      if (
        new Set(checked.map((row) => row.service.trim().toLowerCase())).size >=
        2
      )
        outcomes.add('independent-service-checks');
      for (let index = 1; index < versions.length; index++) {
        const before = versions[index - 1].payload,
          after = versions[index].payload;
        if (
          before.entry_type !== 'transport_decision' ||
          after.entry_type !== 'transport_decision'
        )
          continue;
        for (const row of after.services) {
          const old = before.services.find(
            (item) => item.row_id === row.row_id
          );
          if (
            old?.applied &&
            row.applied &&
            !sameJson(old.applied, row.applied)
          ) {
            outcomes.add('transport-correction');
            if (old.checked && !row.checked)
              outcomes.add('replacement-invalidates-checks');
          }
        }
      }
    }
  }
  return [...outcomes];
}
