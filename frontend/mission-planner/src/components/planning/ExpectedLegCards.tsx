import type { PlanningView } from '../../types/planning';
import { Link } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/card';
import type { ReactNode } from 'react';
import { planningDisplayCount } from '../../services/planning';
export function ExpectedLegCards({
  view,
  renderInstalledActions,
}: {
  view: PlanningView;
  renderInstalledActions?: (legId: string) => ReactNode;
}) {
  const statuses = {
    awaiting_kml: 'Awaiting KML',
    needs_review: 'Needs review',
    reviewed: 'Reviewed',
  };
  return (
    <section
      aria-label="Itinerary expected legs"
      className="grid min-w-0 gap-4"
    >
      {view.expected_legs
        .filter((card) => !card.leg.retired)
        .sort((a, b) => a.leg.ordinal - b.leg.ordinal)
        .map((card) => (
          <Card key={card.leg.id}>
            <CardHeader>
              <CardTitle>
                Leg {card.leg.ordinal} of {planningDisplayCount(view)}
              </CardTitle>
              <p>
                {card.leg.departure_airport} → {card.leg.arrival_airport}
              </p>
              <p className="text-sm">{statuses[card.review_status]}</p>
              <p className="text-sm text-muted-foreground">
                Computation: {card.computation_status ?? 'idle'}
              </p>
            </CardHeader>
            <CardContent className="min-w-0 space-y-3">
              <p className="break-words text-sm">
                UTC {card.leg.departure_time} → {card.leg.arrival_time}
              </p>
              <p className="text-sm">
                {(card.leg.draft?.ar_corrections?.length
                  ? card.leg.draft.ar_corrections
                  : card.leg.ar_rows
                )?.length ?? 0}{' '}
                AR rows ·{' '}
                {card.leg.ar_section_status === 'unrecognized'
                  ? 'AR section needs correction'
                  : card.leg.ar_section_status === 'empty'
                    ? 'No listed ARs'
                    : 'ARs listed'}
              </p>
              {card.errors?.map((e, i) => (
                <p role="alert" key={i} className="text-sm text-destructive">
                  {e.message}
                </p>
              ))}
              <Link
                className="inline-flex min-h-11 items-center rounded-lg border px-4 font-semibold text-primary focus-visible:outline-2"
                to={`/missions/${encodeURIComponent(view.mission.id)}/legs/${encodeURIComponent(card.leg.id)}`}
              >
                {card.review_status === 'awaiting_kml'
                  ? 'Upload KML'
                  : card.review_status === 'reviewed'
                    ? 'Open reviewed plan'
                    : 'Review leg'}
              </Link>
              {card.leg.installed_leg_id &&
                renderInstalledActions?.(card.leg.installed_leg_id)}
            </CardContent>
          </Card>
        ))}
    </section>
  );
}
