import type { ReadRecord, SavedRecord } from '@/types/operator';
interface Props {
  items: ReadRecord[];
  context?: { name: string; legs: { id: string; name: string }[] };
  disabled: boolean;
  onEdit: (record: SavedRecord) => void;
  onHistory: (id: string) => void;
  onTransition: (record: SavedRecord) => void;
}
const button =
  'min-h-11 rounded-md border px-3 py-2 text-sm disabled:opacity-50';
export function JournalList({
  items,
  context,
  disabled,
  onEdit,
  onHistory,
  onTransition,
}: Props) {
  const legName = (id: string | null) =>
    context?.legs.find((leg) => leg.id === id)?.name ?? id ?? 'unknown';
  return (
    <section className="min-w-0 space-y-3" aria-label="Current journal entries">
      <h2 className="text-lg font-semibold">Current entries</h2>
      {items.length === 0 && <p>No journal entries.</p>}
      {items.map(({ record, association }) => (
        <article
          key={record.record_id}
          className="min-w-0 space-y-2 break-words rounded-lg border bg-card p-4 [overflow-wrap:anywhere]"
        >
          <h3 className="font-semibold">{record.payload.title}</h3>
          <p className="whitespace-pre-wrap">{record.payload.note}</p>
          <p className="text-sm text-muted-foreground">
            {record.scope} ·{' '}
            {context
              ? record.scope === 'leg'
                ? legName(record.leg_id)
                : context.name
              : (record.leg_id ?? record.mission_id)}{' '}
            · version {record.version}
            {record.deleted ? ' · Removed' : ''}
          </p>
          <p className="text-sm">
            {record.time.occurred_at
              ? `${record.time.occurred_at} (UTC, ${record.time.precision})`
              : 'Occurrence time unknown'}
          </p>
          {record.scope === 'between_legs' && (
            <p className="text-sm">
              Previous leg: {legName(record.payload.previous_leg_id)} · Next
              leg: {legName(record.payload.next_leg_id)}
            </p>
          )}
          {association.status !== 'resolved' && (
            <p role="status">
              Association {association.status}: retained mission{' '}
              {record.mission_id}
              {record.leg_id ? `, leg ${record.leg_id}` : ''}
              {association.unresolved_fields.length
                ? `; missing ${association.unresolved_fields.join(', ')}`
                : ''}
              . Edit to reassociate.
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            {!record.deleted && (
              <button
                className={button}
                disabled={disabled}
                onClick={() => onEdit(record)}
                aria-label={`Edit ${record.payload.title}`}
              >
                Edit
              </button>
            )}
            <button
              className={button}
              onClick={() => onHistory(record.record_id)}
              aria-label={`History for ${record.payload.title}`}
            >
              History
            </button>
            <button
              className={button}
              disabled={disabled}
              onClick={() => onTransition(record)}
              aria-label={`${record.deleted ? 'Restore' : 'Remove'} ${record.payload.title}`}
            >
              {record.deleted ? 'Restore' : 'Remove'}
            </button>
          </div>
        </article>
      ))}
    </section>
  );
}
