import type {
  BatchRoutePreview,
  ExpectedLeg,
  PlanningView,
} from '../../types/planning';
import { BatchRouteAttachments } from './BatchRouteAttachments';
import { Button } from '../ui/button';
import { Input } from '../ui/input';

export function ItineraryIntake({
  view,
  initialFiles,
  initialPreview,
  onChange,
  onContinue,
}: {
  view: PlanningView;
  initialFiles: File[];
  initialPreview: BatchRoutePreview | null;
  onChange: (view: PlanningView) => void;
  onContinue: () => void;
}) {
  return (
    <section aria-label="Itinerary intake" className="space-y-4">
      <p role="status">
        Draft retained. Attach sources → Review AR windows → Optimize plans →
        Final review.
      </p>
      <BatchRouteAttachments
        key={view.mission.id}
        view={view}
        initialFiles={initialFiles}
        initialPreview={initialPreview}
        onAccepted={onChange}
      />
      {view.expected_legs.some(
        (card) => !card.leg.retired && !card.leg.route
      ) && (
        <p>
          Some routes are still pending. You can resume attachments in the
          mission workspace; route-dependent planning remains blocked.
        </p>
      )}
      <Button onClick={onContinue}>Continue to source review</Button>
    </section>
  );
}

/** Source values can be corrected before route-dependent occurrence review. */
export function ItinerarySourceLeg({
  leg,
  onChange,
}: {
  leg: ExpectedLeg;
  onChange: (updates: Partial<ExpectedLeg>) => void;
}) {
  return (
    <section className="space-y-3 rounded border p-4">
      <h3 className="font-semibold">Leg {leg.ordinal}</h3>
      <div className="grid gap-3 sm:grid-cols-2">
        {(
          [
            'departure_airport',
            'arrival_airport',
            'departure_time',
            'arrival_time',
          ] as const
        ).map((field) => (
          <label key={field}>
            {field.replaceAll('_', ' ')} (leg {leg.ordinal})
            <Input
              aria-label={`${field.replaceAll('_', ' ')} leg ${leg.ordinal}`}
              value={leg[field]}
              onChange={(event) => onChange({ [field]: event.target.value })}
            />
          </label>
        ))}
      </div>
      <p>
        {leg.ar_rows?.length ?? 0} source AR rows. Route occurrences and AR
        confirmation are pending route attachment.
      </p>
      {leg.ar_section_status === 'unrecognized' && (
        <p role="alert">
          AR source section needs correction during source review.
        </p>
      )}
      {(leg.ar_rows ?? []).map((row) => (
        <details key={row.id}>
          <summary>
            {row.track}:{' '}
            {row.confirmed_units === 'flight_level'
              ? `FL${row.source_altitude ?? '?'}`
              : `${row.source_altitude ?? '?'} ${row.confirmed_units ?? 'units required'}`}
          </summary>
          <p className="break-words text-sm">{row.source_text}</p>
          {(
            ['track', 'entry_time', 'exit_time', 'source_altitude'] as const
          ).map((field) => (
            <label key={field}>
              {field.replaceAll('_', ' ')} {row.track}
              <Input
                aria-label={`Source ${field.replaceAll('_', ' ')} ${row.track} leg ${leg.ordinal}`}
                type={field === 'source_altitude' ? 'number' : 'text'}
                value={row[field] ?? ''}
                onChange={(event) =>
                  onChange({
                    ar_rows: (leg.ar_rows ?? []).map((item) =>
                      item.id === row.id
                        ? {
                            ...item,
                            [field]:
                              field === 'source_altitude'
                                ? event.target.value
                                  ? Number(event.target.value)
                                  : null
                                : event.target.value,
                            confirmed: false,
                          }
                        : item
                    ),
                  })
                }
              />
            </label>
          ))}
        </details>
      ))}
    </section>
  );
}
