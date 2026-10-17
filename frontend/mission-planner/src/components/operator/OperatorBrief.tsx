import { preparationAt } from './callTiming';
import { Link } from 'react-router-dom';
import type { ReadRecord, RecordPage } from '@/types/operator';
interface Props {
  missionId: string;
  pages: RecordPage[];
  unavailable: boolean;
  loading: boolean;
  failed: boolean;
  incomplete: boolean;
}
function operatorUtc(value: string | null | undefined) {
  if (!value || !Number.isFinite(Date.parse(value))) return 'Time unknown';
  return new Date(value)
    .toISOString()
    .replace('T', ' ')
    .replace(/\.\d+Z$/, ' UTC');
}
function SummaryRecord({ item, now }: { item: ReadRecord; now: number }) {
  const { record, freshness, association } = item;
  const prep = preparationAt(record);
  const source = {
    modeled: 'Modeled',
    observed: 'Observed',
    operator_reported: 'Operator reported',
  }[record.provenance.kind];
  return (
    <div className="min-w-0 space-y-1 break-words [overflow-wrap:anywhere]">
      <p className="font-medium">{record.payload.title}</p>
      <p className="text-sm">
        {operatorUtc(record.time.planned_start_at ?? record.time.occurred_at)}
      </p>
      {record.payload.entry_type === 'call' && (
        <p className="text-sm">Status: {record.payload.status}</p>
      )}
      {prep && (
        <p className="text-sm">
          Prepare: {operatorUtc(prep)} ·{' '}
          {Date.parse(prep) <= now ? 'Due at snapshot' : 'Upcoming at snapshot'}
        </p>
      )}
      {record.payload.entry_type === 'call' &&
        record.payload.status === 'scheduled' &&
        Date.parse(record.time.planned_start_at ?? '') < now && (
          <p className="text-sm text-amber-400">
            Past planned start · still scheduled.
          </p>
        )}
      <p className="text-xs text-muted-foreground">
        {source} · freshness {freshness.status} · association{' '}
        {association.status} · {record.scope.replaceAll('_', ' ')}
        {record.leg_id ? ` · ${record.leg_id}` : ''}
      </p>
    </div>
  );
}
export function OperatorBrief({
  missionId,
  pages,
  unavailable,
  loading,
  failed,
  incomplete,
}: Props) {
  if (!missionId)
    return (
      <section
        aria-label="Mission workspace"
        className="rounded-xl border bg-card p-5"
      >
        <h2 className="text-lg font-semibold">Choose a mission</h2>
        <p className="mt-2 text-muted-foreground">
          Open a mission below to review requirements, risks, issues and journal
          entries.
        </p>
        <Link
          className="mt-3 inline-flex min-h-11 items-center underline"
          to="/missions"
        >
          Browse missions
        </Link>
      </section>
    );
  const asOf = pages[0]?.as_of;
  const now = asOf ? Date.parse(asOf) : NaN;
  const items = pages
    .flatMap((p) => p.items)
    .filter((i) => !i.record.deleted && i.record.mission_id === missionId);
  const timed = items
    .filter((i) => {
      const start = Date.parse(i.record.time.planned_start_at ?? '');
      const end = Date.parse(i.record.time.planned_end_at ?? '');
      return (
        Number.isFinite(now) &&
        Number.isFinite(start) &&
        (start >= now || end > now)
      );
    })
    .sort(
      (a, b) =>
        Date.parse(a.record.time.planned_start_at!) -
        Date.parse(b.record.time.planned_start_at!)
    );
  const context = [...items].sort(
    (a, b) => b.record.journal_seq - a.record.journal_seq
  )[0]?.record;
  const scheduledCalls = items
    .filter(
      (i) =>
        i.record.payload.entry_type === 'call' &&
        ['tentative', 'scheduled', 'delayed'].includes(
          i.record.payload.status
        ) &&
        Number.isFinite(Date.parse(i.record.time.planned_start_at ?? ''))
    )
    .sort(
      (a, b) =>
        Date.parse(a.record.time.planned_start_at!) -
        Date.parse(b.record.time.planned_start_at!)
    );
  const call = scheduledCalls.find(
    (i) => Date.parse(i.record.time.planned_start_at!) >= now
  );
  const overdueCalls = scheduledCalls.filter(
    (i) => Date.parse(i.record.time.planned_start_at!) < now
  );
  const risk = timed.find((i) => i.record.record_type === 'risk');
  const issues = items.filter(
    (i) =>
      i.record.payload.entry_type === 'issue' &&
      i.record.payload.status === 'open'
  );
  const unknownTimes = items.filter(
    (i) =>
      (i.record.record_type === 'risk' ||
        (i.record.payload.entry_type === 'call' &&
          ['tentative', 'scheduled', 'delayed'].includes(
            i.record.payload.status
          ))) &&
      !Number.isFinite(Date.parse(i.record.time.planned_start_at ?? ''))
  );
  const problem =
    unavailable || failed
      ? 'Summary unavailable. Saved state could not be verified.'
      : loading
        ? 'Loading summary…'
        : incomplete
          ? 'Summary incomplete. Load remaining records.'
          : null;
  const cards = [
    {
      title: 'Next requirement',
      rows: call ? [call] : [],
      empty: 'No recorded upcoming requirements.',
    },
    {
      title: 'Next risk',
      rows: risk ? [risk] : [],
      empty:
        'No recorded upcoming risks. Modeled availability is not measured service health.',
    },
    {
      title: 'Issues',
      rows: issues.slice(0, 3),
      empty: 'No recorded open issues.',
    },
  ];
  return (
    <section aria-label="Mission workspace" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="min-w-0 break-words font-medium [overflow-wrap:anywhere]">
          Mission {missionId}
        </p>
        <p className="text-xs text-muted-foreground">
          Snapshot {operatorUtc(asOf)} · refresh to update
        </p>
      </div>
      {!unavailable && !failed && context && (
        <p className="text-sm text-muted-foreground">
          Latest recorded context: {context.scope.replaceAll('_', ' ')}
          {context.leg_id ? ` · ${context.leg_id}` : ''}. This is a record
          association, not flight-phase telemetry.
        </p>
      )}
      {incomplete && (
        <p role="status">
          More records available; summaries cover loaded records only.
        </p>
      )}
      <div className="grid min-w-0 gap-3 lg:grid-cols-3">
        {cards.map((card) => (
          <section
            key={card.title}
            aria-label={card.title}
            className="min-w-0 space-y-3 rounded-xl border bg-card p-4"
          >
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              {card.title}
            </h2>
            {problem ? (
              <p className="text-sm">{problem}</p>
            ) : card.rows.length ? (
              card.rows.map((item) => (
                <SummaryRecord
                  key={item.record.record_id}
                  item={item}
                  now={now}
                />
              ))
            ) : (
              <p className="text-sm text-muted-foreground">{card.empty}</p>
            )}
            {!problem && card.title === 'Issues' && issues.length > 3 && (
              <details>
                <summary className="min-h-11 cursor-pointer py-2 text-sm">
                  {issues.length - 3} more recorded open issues
                </summary>
                <div className="space-y-3">
                  {issues.slice(3).map((item) => (
                    <SummaryRecord
                      key={item.record.record_id}
                      item={item}
                      now={now}
                    />
                  ))}
                </div>
              </details>
            )}
          </section>
        ))}
      </div>
      {!problem && overdueCalls.length > 0 && (
        <section
          aria-label="Attention needed"
          className="space-y-3 rounded-xl border border-amber-400/40 bg-card p-4"
        >
          <h2 className="text-sm font-semibold uppercase tracking-wide text-amber-400">
            Attention needed
          </h2>
          <p className="text-sm text-muted-foreground">
            These calls are past their planned start and remain active.
          </p>
          <div className="grid min-w-0 gap-4 lg:grid-cols-3">
            {overdueCalls.map((item) => (
              <SummaryRecord
                key={item.record.record_id}
                item={item}
                now={now}
              />
            ))}
          </div>
        </section>
      )}
      {!problem && unknownTimes.length > 0 && (
        <p className="text-sm text-muted-foreground">
          {unknownTimes.length} requirement/risk record(s) have unknown planned
          timing and cannot be ordered.
        </p>
      )}
      <p className="text-xs text-muted-foreground">
        Summaries reflect saved records, not verified service health. Transition
        advisories do not by themselves indicate an outage.
      </p>
    </section>
  );
}
