import type { GfsView } from './gfs-controller';
import './AviationWeather.css';
const utc = (value: number) =>
  new Date(value).toISOString().slice(0, 16).replace('T', ' ') + ' UTC';
export function GfsStatus({ view }: { view: GfsView }) {
  if (view.state === 'off') return null;
  const product = view.products.winds ?? view.products.temperature,
    vertical = product?.vertical;
  const level =
    vertical?.kind === 'pressure'
      ? `${vertical.pressure_pa / 100} hPa`
      : vertical?.kind === 'flight-level'
        ? `FL${String(vertical.flight_level).padStart(3, '0')} · ${vertical.derivation === 'native' ? 'native' : 'ISA / log-pressure interpolation'}`
        : '';
  return (
    <details className="gfs-status" aria-label="Flight-level atmosphere status">
      <summary>
        NOAA GFS ·{' '}
        {view.state === 'current'
          ? 'Current'
          : view.state === 'stale'
            ? 'Stale'
            : view.state === 'loading'
              ? 'Loading'
              : 'Unavailable'}
        {level && ` · ${level}`}
      </summary>
      {product && (
        <p>
          Run {utc(product.run_at_ms!)}
          <br />
          Valid {utc(product.valid_at_ms!)} · F
          {String(product.lead_seconds! / 3600).padStart(3, '0')}
        </p>
      )}
      {view.products.winds && (
        <p>
          Wind FROM · kt · 50 / 10 / 5 knot pennants and feathers; circle =
          calm. Deterministic equal-area thinning, at most 2,000 barbs.
        </p>
      )}
      {view.products.temperature && (
        <>
          <p>Air temperature · °C · fixed −80 to +40 scale; ends clamped.</p>
          <div className="gfs-temperature-legend" aria-hidden="true" />
          <p className="gfs-legend-labels">
            <span>−80 °C</span>
            <span>−20 °C</span>
            <span>+40 °C</span>
          </p>
        </>
      )}
      <p>
        Masked or unavailable cells mean unknown weather. Model guidance;
        Surface is unsupported.
      </p>
    </details>
  );
}
