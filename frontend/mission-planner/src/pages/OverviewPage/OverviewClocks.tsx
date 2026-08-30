import { useId } from 'react';
import type { OverviewClockPreference } from './preferences';
import { formatOverviewClock } from './useOverviewClock';

export interface OverviewClocksProps {
  clocks: readonly OverviewClockPreference[];
  now: Date;
  expanded: boolean;
  onExpandedChange(expanded: boolean): void;
}

function ClockCard({
  clock,
  now,
}: {
  clock: OverviewClockPreference;
  now: Date;
}) {
  const formatted = formatOverviewClock(now, clock.timeZone);

  return (
    <article className="rounded-md border bg-card p-3 text-card-foreground">
      <h3 className="text-sm font-medium">{clock.label}</h3>
      {formatted ? (
        <>
          <time
            className="block font-mono text-2xl tabular-nums"
            dateTime={formatted.dateTime}
            aria-label={`${clock.label}: ${formatted.time}, ${formatted.zoneAndOffset}`}
          >
            {formatted.time}
          </time>
          <p className="text-xs text-muted-foreground">
            {formatted.zoneAndOffset}
          </p>
        </>
      ) : (
        <p className="text-sm text-muted-foreground">Time unavailable</p>
      )}
    </article>
  );
}

export function OverviewClocks({
  clocks,
  now,
  expanded,
  onExpandedChange,
}: OverviewClocksProps) {
  const additionalId = useId();
  const [utc, ...additional] = clocks;

  return (
    <section className="space-y-3">
      {utc ? <ClockCard clock={utc} now={now} /> : null}
      <button
        type="button"
        className="min-h-11 min-w-11 rounded-md border px-3 py-2 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-expanded={expanded}
        aria-controls={additionalId}
        onClick={() => onExpandedChange(!expanded)}
      >
        Additional clocks
      </button>
      <div
        id={additionalId}
        hidden={!expanded}
        className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
      >
        {additional.map((clock) => (
          <ClockCard key={clock.id} clock={clock} now={now} />
        ))}
      </div>
    </section>
  );
}
