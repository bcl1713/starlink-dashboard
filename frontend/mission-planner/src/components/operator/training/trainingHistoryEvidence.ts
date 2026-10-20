import type { RecordEvidenceSource } from './trainingEvidence';
import { sameRecord } from './trainingRecordIdentity';

/** Verify the complete chain for every current record, including tombstones. */
export function hasCompleteImmutableHistory(
  source: RecordEvidenceSource
): boolean {
  if (
    !source.ready ||
    !source.complete ||
    !source.historyComplete ||
    !source.fresh ||
    !source.records.length ||
    !source.records.some((row) => row.version > 1)
  )
    return false;
  return source.records.every((current) => {
    if (
      !Number.isInteger(current.version) ||
      current.version < 1 ||
      current.mission_id !== source.missionId ||
      current.provenance.source_mode !== 'simulation'
    )
      return false;
    const revisions = source.history.filter(
      (row) => row.record_id === current.record_id
    );
    if (
      source.prerequisiteIds.includes(current.record_id) &&
      current.version === 1 &&
      !revisions.length
    )
      revisions.push(current);
    const versions = new Map<number, typeof current>();
    for (const revision of revisions) {
      const previous = versions.get(revision.version);
      if (previous && !sameRecord(previous, revision)) return false;
      versions.set(revision.version, revision);
    }
    const chain = [...versions.values()].sort((a, b) => a.version - b.version);
    return (
      chain.length === current.version &&
      sameRecord(chain[chain.length - 1], current) &&
      new Set(chain.map((row) => row.command_id)).size === chain.length &&
      chain.every(
        (row, index) =>
          row.mission_id === source.missionId &&
          row.provenance.source_mode === 'simulation' &&
          row.version === index + 1 &&
          row.previous_version === (index === 0 ? null : index) &&
          Number.isInteger(row.journal_seq) &&
          row.journal_seq > (index === 0 ? 0 : chain[index - 1].journal_seq)
      )
    );
  });
}
