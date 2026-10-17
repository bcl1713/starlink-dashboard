import type { ReadRecord, SavedRecord } from '@/types/operator';
import { preparationAt } from './callTiming';
import { revisionUtc } from './revisionUtc';
const button = 'min-h-11 rounded-md border px-3 disabled:opacity-50';
export function CallList({
  items,
  disabled,
  incomplete,
  asOf,
  onEdit,
  onHistory,
  onTransition,
}: {
  items: ReadRecord[];
  disabled: boolean;
  incomplete: boolean;
  asOf?: string;
  onEdit: (record: SavedRecord) => void;
  onHistory: (id: string) => void;
  onTransition: (record: SavedRecord) => void;
}) {
  const unique = [
    ...new Map(
      items
        .filter((i) => i.record.record_type === 'call')
        .map((i) => [i.record.record_id, i])
    ).values(),
  ];
  const ordered = unique.sort((a, b) => {
    const av = Date.parse(a.record.time.planned_start_at ?? '');
    const bv = Date.parse(b.record.time.planned_start_at ?? '');
    const delta =
      (Number.isFinite(av) ? av : Infinity) -
      (Number.isFinite(bv) ? bv : Infinity);
    return (
      (Number.isNaN(delta) ? 0 : delta) ||
      a.record.record_id.localeCompare(b.record.record_id)
    );
  });
  const active = ordered.filter(
    (i) =>
      !i.record.deleted &&
      i.record.payload.entry_type === 'call' &&
      !['completed', 'cancelled'].includes(i.record.payload.status)
  );
  function rows(values: ReadRecord[]) {
    return values.map((item) => {
      const r = item.record;
      if (r.payload.entry_type !== 'call') return null;
      const prep = preparationAt(r);
      return (
        <li
          key={r.record_id}
          className="min-w-0 space-y-2 break-words rounded-lg border p-3 [overflow-wrap:anywhere]"
        >
          <h4 className="font-semibold">
            {r.payload.party ?? r.payload.title}
          </h4>
          <p className="text-sm">
            {r.deleted ? 'Removed · ' : ''}
            {r.payload.status === 'cancelled'
              ? 'Canceled'
              : r.payload.status} ·{' '}
            {r.payload.communications_kind ?? 'Type unknown'}
          </p>
          <p className="text-sm">
            Planned: {revisionUtc(r.time.planned_start_at)} · End:{' '}
            {revisionUtc(r.time.planned_end_at)}
          </p>
          <p className="text-sm">
            Actual: {revisionUtc(r.time.occurred_at)} · End:{' '}
            {revisionUtc(r.time.ended_at)}
          </p>
          {prep && (
            <p className="text-sm">
              Prepare: {revisionUtc(prep)}
              {asOf
                ? Date.parse(prep) <= Date.parse(asOf)
                  ? ' · Due at snapshot'
                  : ' · Upcoming at snapshot'
                : ''}
            </p>
          )}
          <p className="text-xs text-muted-foreground">
            Operator reported · freshness {item.freshness.status} · association{' '}
            {item.association.status} · {r.scope.replaceAll('_', ' ')}
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              className={button}
              disabled={disabled || r.deleted}
              onClick={() => onEdit(r)}
            >
              Edit call
            </button>
            <button className={button} onClick={() => onHistory(r.record_id)}>
              Call history
            </button>
            <button
              className={button}
              disabled={disabled}
              onClick={() => onTransition(r)}
            >
              {r.deleted ? 'Restore call' : 'Remove call'}
            </button>
          </div>
        </li>
      );
    });
  }
  return (
    <div className="min-w-0 space-y-3" aria-label="Call list">
      {incomplete && (
        <p role="status">
          Call list incomplete. Load more calls to include remaining records.
        </p>
      )}
      <h3 className="font-semibold">Active requirements</h3>
      {!active.length && <p>No recorded active requirements.</p>}
      <ul className="space-y-3">
        {rows(active.filter((i) => !!i.record.time.planned_start_at))}
      </ul>
      {active.some((i) => !i.record.time.planned_start_at) && (
        <>
          <h4 className="font-medium">Unknown planned timing</h4>
          <ul className="space-y-3">
            {rows(active.filter((i) => !i.record.time.planned_start_at))}
          </ul>
        </>
      )}
      <details>
        <summary className="min-h-11 cursor-pointer py-2">
          Completed, canceled and removed calls
        </summary>
        <ul className="space-y-3">
          {rows(ordered.filter((i) => !active.includes(i)))}
        </ul>
      </details>
    </div>
  );
}
