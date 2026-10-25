import { useTransportAvailability } from '@/hooks/api/useTransportAvailability';
import { legAvailability } from '@/services/transportAvailability';
import { useQuery } from '@tanstack/react-query';
import type { ExpectedLegCard, PlanningView } from '../../types/planning';
import { usePlanning } from '../../hooks/api/usePlanning';
import { usePlanningLegWorkflow } from '../../hooks/usePlanningLegWorkflow';
import { planningApi } from '../../services/planning';
import { routesApi } from '../../services/routes';
import { ARReview } from './ARReview';
import { Button } from '../ui/button';

export function ItinerarySourceReview({ view }: { view: PlanningView }) {
  return (
    <section aria-label="Itinerary source review" className="space-y-4">
      <h2 className="font-semibold">Review source inputs</h2>
      <p>
        Review the displayed AR intervals and heights, or confirm no ARs.
        Changes save automatically; satellite access and Starshield settings are
        inherited from intake.
      </p>
      {view.expected_legs
        .filter((card) => !card.leg.retired)
        .map((card) => (
          <SourceLeg key={card.leg.id} card={card} view={view} />
        ))}
    </section>
  );
}
function SourceLeg({
  card,
  view,
}: {
  card: ExpectedLegCard;
  view: PlanningView;
}) {
  const planning = usePlanning(view.mission.id, false);
  const availability = useTransportAvailability(view.mission.id);
  const availableTransports = legAvailability(availability.data, card.leg.id);
  const xAvailable =
    availableTransports?.x_configuration_required ??
    availableTransports?.planned.X !== false;
  const options = useQuery({
    queryKey: ['planning-satellite-options'],
    queryFn: planningApi.satelliteOptions,
    retry: false,
  });
  const coordinates = useQuery({
    queryKey: ['planning-route-detail', card.leg.route?.route_id],
    queryFn: () => routesApi.get(card.leg.route!.route_id),
    enabled: !!card.leg.route,
  });
  const workflow = usePlanningLegWorkflow({
    card,
    view,
    planning,
    satelliteOptions: options.data,
    xAvailable,
    navigate: () => {},
    onAcceptedRoute: () => {},
  });
  const leg = card.leg;
  if (!leg.route)
    return (
      <p>Leg {leg.ordinal}: attach a route before reviewing occurrences.</p>
    );
  return (
    <fieldset
      disabled={workflow.pending}
      className="space-y-3 rounded border p-4"
    >
      <legend>
        Leg {leg.ordinal}: {leg.departure_airport} → {leg.arrival_airport}
      </legend>
      <p>
        Permitted X-band:{' '}
        {xAvailable
          ? (workflow.draft.permitted_satellite_ids ?? []).join(', ') ||
            'not configured'
          : 'unavailable for this leg'}{' '}
        · Starshield{' '}
        {(availableTransports?.planned.Ku ??
        workflow.draft.starshield_enabled ??
        true)
          ? 'available'
          : 'unavailable'}
      </p>
      {workflow.error && <p role="alert">{workflow.error}</p>}
      {workflow.error && workflow.dirty && (
        <Button onClick={() => void workflow.save()}>Retry source save</Button>
      )}
      {workflow.dirty && (
        <p role="status">
          {workflow.pending
            ? 'Saving source review…'
            : 'Source changes pending save.'}
        </p>
      )}
      <ARReview
        leg={leg}
        rows={workflow.draft.ar_corrections ?? leg.ar_rows ?? []}
        onChange={(rows) => workflow.change({ ar_corrections: rows })}
        sectionStatus={workflow.section}
        onSectionStatusChange={(value) => {
          workflow.setSection(value);
          workflow.change({ no_ars_confirmed: false });
        }}
        noARsConfirmed={workflow.draft.no_ars_confirmed ?? false}
        onNoARsConfirmedChange={(value) =>
          workflow.change({ no_ars_confirmed: value })
        }
        coordinates={(coordinates.data?.points ?? []).map((point) => [
          point.latitude,
          point.longitude,
        ])}
        routePoints={coordinates.data?.points ?? []}
      />
      {(coordinates.error || options.error) && (
        <p role="alert">
          Source geometry or satellite options could not be loaded. Reload
          before review.
        </p>
      )}
    </fieldset>
  );
}
