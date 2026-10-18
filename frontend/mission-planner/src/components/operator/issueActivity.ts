import type { SavedRecord } from '@/types/operator';
export interface IssueMessage {
  rootVersion: number;
  selected: SavedRecord;
  text: string;
  effectiveAt: string | null;
  recordedAt: string;
  corrected: boolean;
  original: SavedRecord;
}
export interface IssueActivityResult {
  updates: IssueMessage[];
  lifecycle: { record: SavedRecord; status: string }[];
}
export function projectIssueActivity(
  revisions: SavedRecord[]
): IssueActivityResult {
  const roots = new Map<number, number>();
  const updates = new Map<number, IssueMessage>();
  const lifecycle: IssueActivityResult['lifecycle'] = [];
  let previousStatus: string | undefined;
  for (const record of [...revisions].sort(
    (a, b) => a.journal_seq - b.journal_seq
  )) {
    if (record.payload.entry_type !== 'issue') continue;
    const payload = record.payload;
    if (record.operation === 'create' || record.operation === 'update') {
      if (!payload.corrects_version && payload.status !== previousStatus)
        lifecycle.push({ record, status: payload.status });
      if (payload.update_text?.trim()) {
        const root = payload.corrects_version
          ? roots.get(payload.corrects_version)
          : record.version;
        if (root === undefined)
          throw new Error('Incomplete correction history');
        roots.set(record.version, root);
        updates.set(root, {
          rootVersion: root,
          selected: record,
          text: payload.update_text,
          effectiveAt: payload.corrects_version
            ? (payload.corrected_update_at ?? null)
            : record.time.occurred_at,
          recordedAt: record.recorded_at,
          corrected: !!payload.corrects_version,
          original: updates.get(root)?.original ?? record,
        });
      }
    }
    previousStatus = payload.status;
  }
  return {
    lifecycle,
    updates: [...updates.values()].sort((a, b) => {
      if (a.effectiveAt === null)
        return b.effectiveAt === null
          ? a.original.journal_seq - b.original.journal_seq
          : 1;
      if (b.effectiveAt === null) return -1;
      return (
        Date.parse(a.effectiveAt) - Date.parse(b.effectiveAt) ||
        a.original.journal_seq - b.original.journal_seq
      );
    }),
  };
}
