import type { RecordPage } from '@/types/operator';
import { operatorUtc } from './issueForms';
export function IssueFollowups({
  pages,
  incomplete,
  unavailable,
}: {
  pages: RecordPage[];
  incomplete: boolean;
  unavailable: boolean;
}) {
  const asOf = pages[0]?.as_of;
  const due = pages
    .flatMap((p) => p.items)
    .filter(
      (i) =>
        !i.record.deleted &&
        i.record.payload.entry_type === 'issue' &&
        i.record.payload.status !== 'resolved' &&
        ['due', 'overdue'].includes(i.follow_up?.state ?? '')
    );
  const unknown = pages
    .flatMap((p) => p.items)
    .some(
      (i) =>
        i.record.payload.entry_type === 'issue' &&
        !i.record.deleted &&
        (!i.follow_up || i.follow_up.state === 'unknown')
    );
  return (
    <aside
      aria-label="Issue follow-up snapshot"
      className="min-w-0 rounded border bg-background p-3 text-sm shadow"
    >
      <a
        className="inline-flex min-h-11 items-center font-medium underline"
        href="#operator-issues"
      >
        Issue follow-ups
      </a>
      {' · '}
      {unavailable || incomplete || !asOf || unknown
        ? 'Snapshot unavailable, stale or incomplete; refresh to verify follow-ups.'
        : due.length
          ? `${due.length} follow-up${due.length === 1 ? '' : 's'} due in this snapshot.`
          : 'No due follow-ups recorded in this snapshot.'}
      <span className="block text-xs text-muted-foreground">
        As of {operatorUtc(asOf)} · snapshot only; refresh to update.
      </span>
    </aside>
  );
}
