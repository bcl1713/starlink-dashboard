import type { AviationView } from './aviation-controller';
import { activeFeatures } from '@/services/aviation-features';
import type { AviationLayer } from '@/services/aviation-weather';
import './AviationWeather.css';
export function AviationStatus({
  view,
  onInspect,
}: {
  view: AviationView;
  onInspect?: () => void;
}) {
  const enabled = (['metar', 'taf', 'sigmet'] as AviationLayer[]).filter(
    (l) => view.layers[l].state !== 'off'
  );
  if (!enabled.length) return null;
  const hasReports = enabled.some(
    (l) =>
      view.layers[l].data &&
      activeFeatures(view.layers[l].data!, l, view.now).length
  );
  return (
    <section
      className="overview-weather-status aviation-weather-status"
      aria-label="Aviation weather status"
    >
      {enabled.map((layer) => {
        const item = view.layers[layer];
        const data = item.data;
        const active = data ? activeFeatures(data, layer, view.now) : [];
        return (
          <div key={layer} className="aviation-product-status">
            <p className="overview-weather-status__state" role="status">
              {
                {
                  metar: 'METAR / SPECI observations',
                  taf: 'TAF terminal forecasts',
                  sigmet: 'International SIGMET advisories',
                }[layer]
              }{' '}
              · {item.state}
            </p>
            {data && (
              <p>
                {active.length} {layer === 'sigmet' ? 'advisories' : 'stations'}{' '}
                · AWC ·{' '}
                {Math.max(
                  0,
                  Math.floor((view.now - data.retrieved_at_ms) / 60000)
                )}{' '}
                min old
                {layer === 'sigmet' &&
                  ` · ${active.filter((f) => !f.geometry).length} unlocated`}
              </p>
            )}
          </div>
        );
      })}
      <p className="aviation-coverage-note">
        Coverage unknown or partial · missing reports mean unknown weather
      </p>
      <button
        type="button"
        className="aviation-inspect-button"
        disabled={!hasReports}
        onClick={onInspect}
      >
        Inspect weather reports
      </button>
      <p className="aviation-inspect-hint">
        Click or tap a marker or advisory to inspect.
      </p>
      <p
        className="overview-weather-legend"
        aria-label="Aviation weather legend"
      >
        <span>● observation</span>
        <span>◇ terminal forecast</span>
        <span>Amber area: advisory</span>
        {[
          ['VFR', '#4ade80'],
          ['MVFR', '#60a5fa'],
          ['IFR', '#f87171'],
          ['LIFR', '#c084fc'],
          ['Unknown', '#9ca3af'],
        ].map(([label, color]) => (
          <span key={label}>
            <i style={{ background: color }} aria-hidden="true" />
            {label}
          </span>
        ))}
      </p>
    </section>
  );
}
