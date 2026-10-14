import type { GfsView } from './gfs-controller';
import { WIND_COLOR_STOPS, windLegendGradient } from './wind-scale';
import './AviationWeather.css';

/** A compact key for admitted map layers; exceptions belong in Map status. */
export function GfsStatus({ view }: { view: GfsView }) {
  const product = view.products.winds ?? view.products.temperature;
  if (!product || !view.drawing || !['current', 'stale'].includes(view.state))
    return null;
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
        <div className="gfs-legend__wind">
          <p>Wind speed · kt</p>
          <div
            className="gfs-wind-legend"
            role="img"
            aria-label="Wind speed color scale, 0 to 150 or more knots"
            style={{ background: windLegendGradient() }}
          />
          <div className="gfs-wind-legend__labels">
            {WIND_COLOR_STOPS.map((s, i) => (
              <span
                key={s.knots}
                style={{
                  left: `${(s.knots / 150) * 100}%`,
                  transform:
                    i === 0
                      ? 'none'
                      : i === WIND_COLOR_STOPS.length - 1
                        ? 'translateX(-100%)'
                        : 'translateX(-50%)',
                }}
              >
                {s.knots === 150 ? '150+' : s.knots}
              </span>
            ))}
          </div>
        </div>
      )}
      {!view.products.winds && view.products.temperature && (
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
