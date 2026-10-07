import type { GfsView } from './gfs-controller';
import './AviationWeather.css';

/** A compact key for admitted map layers; exceptions belong in Map status. */
export function GfsStatus({ view }: { view: GfsView }) {
  const product = view.products.winds ?? view.products.temperature;
  if (!product) return null;
  const vertical = product.vertical;
  const level =
    vertical.kind === 'pressure'
      ? `${vertical.pressure_pa / 100} hPa`
      : vertical.kind === 'flight-level'
        ? `FL${String(vertical.flight_level).padStart(3, '0')}`
        : '';
  const horizon = view.selection?.horizon_hours;
  return (
    <section className="gfs-legend" aria-label="Atmosphere legend">
      <p className="gfs-legend__context">
        NOAA GFS · {level}
        {horizon !== undefined &&
          ` · ${horizon === 0 ? 'Now' : `+${horizon} h`}`}
      </p>
      {view.products.winds && (
        <p className="gfs-legend__wind">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M2 19h20M4 19V5M9 19V5M14 19v-7" />
          </svg>
          <span>Wind · kt</span>
        </p>
      )}
      {view.products.temperature && (
        <div className="gfs-legend__temperature">
          <p>Temperature · °C</p>
          <div className="gfs-temperature-legend" aria-hidden="true" />
          <p className="gfs-legend-labels">
            <span>−80</span>
            <span>−20</span>
            <span>+40</span>
          </p>
        </div>
      )}
    </section>
  );
}
