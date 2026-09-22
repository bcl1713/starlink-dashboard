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

const STATE_MESSAGES: Record<Exclude<OverviewUpcomingPoisState, 'available'>, string> = {
  no_active_route: 'No active route.',
  no_generated_pois: 'No generated POIs.',
  no_upcoming_pois: 'No upcoming POIs.',
  unavailable: 'Upcoming POIs unavailable.',
};

function etaLabel(estimatedArrivalTime: string | null, currentTime: Date): string {
  if (estimatedArrivalTime === null) return 'ETA unavailable';

  const remainingMs = Date.parse(estimatedArrivalTime) - currentTime.valueOf();
  if (!Number.isFinite(remainingMs)) return 'ETA unavailable';
  if (remainingMs <= 0) return 'Due';

  const totalMinutes = Math.ceil(remainingMs / 60_000);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;

  return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
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
                  <td>{etaLabel(poi.estimated_arrival_time, currentTime)}</td>
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
          <p className="upcoming-pois__state" role={state === 'unavailable' ? 'alert' : undefined}>
            {STATE_MESSAGES[state]}
          </p>
        </div>
      )}
    </aside>
  );
}
