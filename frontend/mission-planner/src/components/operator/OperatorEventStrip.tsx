import { useState } from 'react';
import type { OperatorEventsState } from '@/hooks/api/useOperatorEvents';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { OperatorAlertSettings } from './OperatorAlertSettings';
import { OperatorEventFeed } from './OperatorEventFeed';
import { eventUtc } from './eventFormatting';
import { useEventAlerts } from './useEventAlerts';
export function OperatorEventStrip({
  events,
}: {
  events: OperatorEventsState;
}) {
  const [open, setOpen] = useState(false);
  const alerts = useEventAlerts(events);
  const active = (events.snapshot?.events ?? []).filter(
    (event) => event.active
  );
  const now = Date.parse(events.snapshot?.as_of ?? '');
  const next = active.find(
    (event) => event.due_at && Date.parse(event.due_at) > now
  );
  const current = active.filter((event) => event.state === 'active').length;
  const attention = active.filter(
    (event) =>
      event.state === 'overdue' ||
      event.state === 'unknown' ||
      event.freshness !== 'fresh'
  ).length;
  const cue = alerts.batch?.events.filter((event) =>
    active.some(
      (current) =>
        current.notification.generation === event.notification.generation &&
        !current.notification.acknowledged &&
        !current.notification.retired
    )
  );
  return (
    <section
      id="operator-events"
      aria-label="Upcoming operational events"
      className="sticky top-0 z-40 min-w-0 space-y-2 rounded-xl border bg-card/95 p-3 shadow-sm backdrop-blur"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0 flex-1 text-sm">
          <p className="font-semibold">
            Now {current} · Attention {attention}
          </p>
          <p className="truncate">
            Next:{' '}
            {next
              ? `${next.title} · ${eventUtc(next.due_at)}`
              : 'No timed future event recorded'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <button className="min-h-11 rounded-md border px-3 text-sm">
                Open Events
              </button>
            </DialogTrigger>
            <DialogContent className="left-auto right-0 top-0 flex h-dvh w-full max-w-xl translate-x-0 translate-y-0 flex-col rounded-none">
              <DialogTitle>Operational Timeline</DialogTitle>
              <DialogDescription>
                Zulu · requirements, follow-ups and modeled advisories.
                Acknowledgment changes alerts only.
              </DialogDescription>
              <OperatorEventFeed
                events={events}
                onClose={() => setOpen(false)}
              />
            </DialogContent>
          </Dialog>
          <OperatorAlertSettings
            preferences={alerts.preferences}
            onChange={alerts.updatePreferences}
            delivery={alerts.delivery}
            onEnable={alerts.enableOutput}
          />
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        {events.failed
          ? 'Feed unavailable · last known'
          : events.loading
            ? 'Loading events'
            : `Updated ${eventUtc(events.snapshot?.as_of)}`}{' '}
        ·{' '}
        {events.snapshot?.coverage === 'available'
          ? 'Sources available'
          : 'Model coverage partial or unknown'}{' '}
        · {alerts.preferences.enabled ? 'Local cues on' : 'Local cues muted'}
      </p>
      {!!cue?.length && (
        <p
          role="status"
          aria-live="polite"
          aria-atomic="true"
          className="text-sm text-amber-400"
        >
          Local cue: {cue.map((event) => event.title).join(' · ')}
          {alerts.batch!.remaining
            ? ` · ${alerts.batch!.remaining} more in the timeline`
            : ''}
        </p>
      )}
      {alerts.warning && (
        <p className="text-xs text-muted-foreground">{alerts.warning}</p>
      )}
      {alerts.delivery?.coordination === 'unavailable' && (
        <p className="text-xs text-muted-foreground">
          Automatic cues unavailable; use the timeline.
        </p>
      )}
    </section>
  );
}
