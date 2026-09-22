import type {
  OverviewUpcomingPoi,
  OverviewUpcomingPoisResponse,
} from '@/services/overview-upcoming-pois';
import { urgencyColor } from './overview-upcoming-pois';

export type OverviewUpcomingPoisState = OverviewUpcomingPoisResponse['state'];

interface UpcomingPoisPanelProps {
  state: OverviewUpcomingPoisState;
  pois: OverviewUpcomingPoi[];
  currentTime: Date;
}

const STATE_MESSAGES: Record<
  Exclude<OverviewUpcomingPoisState, 'available'>,
  string
> = {
  no_active_route: 'No active route.',
  no_generated_pois: 'No generated POIs.',
  no_upcoming_pois: 'No upcoming POIs.',
  unavailable: 'Upcoming POIs unavailable.',
};

const KIND_LABELS: Record<OverviewUpcomingPoi['kind'], string> = {
  departure: 'Departure',
  arrival: 'Arrival',
  aar_start: 'AAR start',
  aar_end: 'AAR end',
  x_band_transition: 'X-band transition',
  ka_coverage_exit: 'Ka coverage exit',
  ka_coverage_entry: 'Ka coverage entry',
  ka_transition: 'Ka transition',
};

function etaLabel(
  estimatedArrivalTime: string | null,
  etaType: OverviewUpcomingPoi['eta_type']
): string {
  if (estimatedArrivalTime === null || etaType === null)
    return 'ETA unavailable';

  const arrival = new Date(estimatedArrivalTime);
  if (!Number.isFinite(arrival.valueOf())) return 'ETA unavailable';

  const date = arrival.toISOString();
  return `${date.slice(0, 10)} ${date.slice(11, 16)} UTC · ${etaType}`;
}

export function UpcomingPoisPanel({
  state,
  pois,
  currentTime,
}: UpcomingPoisPanelProps) {
  const visiblePois = pois.slice(0, 5);
  const isAvailable = state === 'available';
  const bodyHeight = isAvailable
    ? `${1.5 + visiblePois.length * 2.5}rem`
    : '2.5rem';

  return (
    <aside
      className="upcoming-pois"
      aria-label="Upcoming POIs"
      style={{ overflowY: 'hidden' }}
    >
      <p className="upcoming-pois__title">Upcoming POIs</p>
      {isAvailable ? (
        <div
          className="upcoming-pois__body"
          data-testid="upcoming-pois-body"
          style={{ height: bodyHeight }}
        >
          <table>
            <thead>
              <tr>
                <th aria-hidden="true" />
                <th scope="col">POI</th>
                <th scope="col">Type</th>
                <th scope="col">ETA</th>
              </tr>
            </thead>
            <tbody>
              {visiblePois.map((poi) => (
                <tr key={poi.poi_id}>
                  <td>
                    <span
                      className="upcoming-pois__swatch"
                      style={{
                        backgroundColor: urgencyColor(
                          poi.estimated_arrival_time,
                          currentTime
                        ),
                      }}
                    />
                  </td>
                  <td>{poi.name}</td>
                  <td>{KIND_LABELS[poi.kind]}</td>
                  <td>{etaLabel(poi.estimated_arrival_time, poi.eta_type)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div
          className="upcoming-pois__body"
          data-testid="upcoming-pois-body"
          style={{ height: bodyHeight }}
        >
          <p
            className="upcoming-pois__state"
            role={state === 'unavailable' ? 'alert' : undefined}
          >
            {STATE_MESSAGES[state]}
          </p>
        </div>
      )}
    </aside>
  );
}
