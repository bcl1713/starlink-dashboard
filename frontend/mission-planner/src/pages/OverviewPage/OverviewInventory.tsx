import type {
  ApplicablePoi,
  GroundEntryPoint,
  StatusData,
} from '../../services/monitoring';
import type { Summary } from './history';
import type { Cadence } from './poller';

interface Props {
  status: StatusData | null;
  statusMessage: string;
  latency: Summary;
  packetLoss: Summary;
  gep: GroundEntryPoint | null;
  pois: ApplicablePoi[];
  cadence: Cadence;
  now: Date;
}

const clocks = [
  ['UTC', 'UTC'],
  ['Local', undefined],
  ['Takeoff', 'America/Los_Angeles'],
  ['Landing', 'Europe/London'],
] as const;

const number = (value: number | null | undefined, suffix = '') =>
  value === null || value === undefined
    ? 'Unavailable'
    : `${value.toFixed(1)}${suffix}`;

export function OverviewInventory({
  status,
  statusMessage,
  latency,
  packetLoss,
  gep,
  pois,
  cadence,
  now,
}: Props) {
  return (
    <div className="overview-inventory">
      <section className="overview-clocks" aria-label="Operational clocks">
        {clocks.map(([label, timeZone]) => (
          <div className="overview-card" data-clock={label} key={label}>
            <strong>{label}</strong>
            <time dateTime={now.toISOString()}>
              {new Intl.DateTimeFormat(undefined, {
                timeZone,
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: false,
              }).format(now)}
            </time>
          </div>
        ))}
      </section>

      <section className="overview-grid" aria-label="Live operations data">
        <article className="overview-card overview-map">
          <h2>Current position map</h2>
          <div role="img" aria-label="Current position map">
            {status
              ? `${status.position.latitude.toFixed(4)}, ${status.position.longitude.toFixed(4)}`
              : 'Position unavailable'}
          </div>
          <small>
            {status ? `Source: ${status.source}` : 'No live sample'}
          </small>
        </article>

        <article className="overview-card">
          <h2>Top applicable POIs</h2>
          {pois.length === 0 ? (
            <p>No applicable POIs</p>
          ) : (
            <ol>
              {pois.map((poi) => (
                <li key={poi.poi_id}>
                  <span>{poi.name}</span>{' '}
                  <small>{number(poi.eta_seconds / 60, ' min')}</small>
                </li>
              ))}
            </ol>
          )}
        </article>

        <article className="overview-card">
          <h2>Latency</h2>
          <p className="overview-value">{number(latency.current, ' ms')}</p>
          <p>5-minute min / avg / max</p>
          <p>
            {number(latency.min)} / {number(latency.average)} /{' '}
            {number(latency.max)} ms
          </p>
        </article>

        <article className="overview-card">
          <h2>Throughput</h2>
          <p>
            Download {number(status?.network.throughput_down_mbps, ' Mbps')}
          </p>
          <p>Upload {number(status?.network.throughput_up_mbps, ' Mbps')}</p>
        </article>

        <article className="overview-card">
          <h2>Ground entry point</h2>
          <p>{gep?.available ? gep.display : 'Unavailable'}</p>
          {gep?.available && (
            <small>
              {number(gep.latitude)}, {number(gep.longitude)}
            </small>
          )}
        </article>

        <article className="overview-card">
          <h2>Obstruction</h2>
          <p className="overview-value">
            {number(status?.obstruction.obstruction_percent, '%')}
          </p>
        </article>

        <article className="overview-card">
          <h2>Packet loss</h2>
          <p className="overview-value">{number(packetLoss.current, '%')}</p>
          <p>
            Average {number(packetLoss.average, '%')} · Max{' '}
            {number(packetLoss.max, '%')}
          </p>
        </article>

        <article className="overview-card">
          <h2>Refresh</h2>
          <p>
            Selected interval: {cadence === 'paused' ? 'Paused' : `${cadence}s`}
          </p>
          <p aria-live="polite">{statusMessage}</p>
        </article>
      </section>
    </div>
  );
}
