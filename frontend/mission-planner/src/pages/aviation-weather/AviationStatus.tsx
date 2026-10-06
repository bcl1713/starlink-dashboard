import type { AviationView } from './aviation-controller';
import {
  activeFeatures,
  prevailingForecast,
  type AviationStation,
  type AviationAdvisory,
} from '@/services/aviation-features';
import type { AviationLayer } from '@/services/aviation-weather';
import './AviationWeather.css';
const utc = (n: number | null) =>
  n === null ? 'unknown' : new Date(n).toISOString().replace('.000Z', ' UTC');
const measured = (v: number | null, unit: string) =>
  v === null ? 'unknown' : `${Number(v.toFixed(1))} ${unit}`;
function weatherSummary(
  p: Pick<
    AviationStation['properties'],
    | 'wind_variable'
    | 'wind_direction_deg'
    | 'wind_speed_mps'
    | 'gust_mps'
    | 'visibility_m'
    | 'visibility_lower_bound'
    | 'ceiling_m'
    | 'ceiling_known'
  >
) {
  return `Wind ${p.wind_variable ? 'variable' : measured(p.wind_direction_deg, '°')} ${measured(p.wind_speed_mps, 'm/s')}${p.gust_mps === null ? '' : `, gust ${measured(p.gust_mps, 'm/s')}`} · visibility ${p.visibility_lower_bound ? '≥ ' : ''}${measured(p.visibility_m, 'm')} · ceiling ${!p.ceiling_known ? 'unknown' : p.ceiling_m === null ? 'no reported ceiling' : measured(p.ceiling_m, 'm AGL')}`;
}
function StationReport({
  station,
  now,
}: {
  station: AviationStation;
  now: number;
}) {
  const p = station.properties,
    forecast = p.report_type === 'TAF',
    main = forecast ? prevailingForecast(station, now) : p;
  return (
    <li>
      <strong>
        {p.station_id}{' '}
        {forecast ? 'terminal forecast' : p.report_type + ' observation'}
      </strong>
      <p>
        {forecast
          ? `Issued ${utc(p.issued_at_ms)} · valid [${utc(p.valid_from_ms)}, ${utc(p.valid_to_ms)})`
          : `Observed ${utc(p.observed_at_ms)} · ${Math.max(0, Math.floor((now - p.observed_at_ms!) / 60000))} min old${now >= p.fresh_until_ms ? ' · stale' : ''}`}
      </p>
      <p>
        {main ? weatherSummary(main) : 'No currently valid forecast group'}
        {!forecast
          ? ` · temperature ${measured(p.temperature_k, 'K')} · dewpoint ${measured(p.dewpoint_k, 'K')} · pressure ${measured(p.pressure_pa, 'Pa')}`
          : ''}
      </p>
      {forecast && (
        <ul aria-label={`${p.station_id} forecast groups`}>
          {p.forecast_groups.slice(0, 4).map((g, i) => (
            <li key={i}>
              {g.change_type && g.change_type !== 'FM'
                ? `Forecast alternative ${g.change_type}${g.probability === null ? '' : ` ${g.probability}%`}`
                : `Forecast ${g.change_type ?? 'prevailing'}`}{' '}
              ·{' '}
              {g.valid_from_ms > now
                ? 'future'
                : now >= g.valid_to_ms
                  ? 'ended'
                  : 'currently valid'}{' '}
              [{utc(g.valid_from_ms)}, {utc(g.valid_to_ms)}) ·{' '}
              {weatherSummary(g)}
            </li>
          ))}
        </ul>
      )}
      {forecast && p.forecast_groups.length > 4 && (
        <p>{p.forecast_groups.length - 4} additional groups retained</p>
      )}
      <p className="aviation-bulletin">
        {p.raw_text.slice(0, 500)}
        {p.raw_text.length > 500 ? '…' : ''}
      </p>
    </li>
  );
}
function AdvisoryReport({ advisory }: { advisory: AviationAdvisory }) {
  const p = advisory.properties,
    v = p.vertical;
  return (
    <li>
      <strong>
        {p.phenomenon ?? 'Unknown phenomenon'} {p.severity ?? ''} advisory
        {advisory.geometry ? '' : ' · unlocated'}
      </strong>
      <p>
        Issuer {p.issuer ?? 'unknown'} · FIR {p.fir ?? 'unknown'} · series{' '}
        {p.series ?? 'unknown'} · revision {p.revision ?? 'unknown'}
        {p.amends ? ` · amends ${p.amends}` : ''}
      </p>
      <p>
        Valid [{utc(p.valid_from_ms)}, {utc(p.valid_to_ms)}) · vertical{' '}
        {v.reference === 'unknown'
          ? 'unknown'
          : `${measured(v.lower, v.unit)} – ${measured(v.upper, v.unit)} ${v.reference}`}
      </p>
      <p className="aviation-bulletin">
        {p.raw_text.slice(0, 500)}
        {p.raw_text.length > 500 ? '…' : ''}
      </p>
    </li>
  );
}
export function AviationStatus({ view }: { view: AviationView }) {
  const enabled = (['metar', 'taf', 'sigmet'] as AviationLayer[]).filter(
    (l) => view.layers[l].state !== 'off'
  );
  if (!enabled.length) return null;
  return (
    <section
      className="overview-weather-status aviation-weather-status"
      aria-label="Aviation weather status"
    >
      {enabled.map((layer) => {
        const item = view.layers[layer],
          data = item.data,
          active = data ? activeFeatures(data, layer, view.now) : [],
          reports = data?.features
            .filter((f) => 'station_id' in f.properties)
            .slice(
              0,
              layer === 'metar' && view.layers.taf.state !== 'off'
                ? 2
                : layer === 'taf' && view.layers.metar.state !== 'off'
                  ? 1
                  : 3
            ) as AviationStation[] | undefined;
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
              <>
                <p>
                  Source {data.source_id.toUpperCase()} · retrieved{' '}
                  {utc(data.retrieved_at_ms)} ·{' '}
                  {Math.max(
                    0,
                    Math.floor((view.now - data.retrieved_at_ms) / 60000)
                  )}{' '}
                  min old
                </p>
                <p>
                  Coverage {data.feed_completeness} · {data.omitted_features}{' '}
                  omitted · missing reports mean unknown weather
                </p>
                <p>
                  {active.length} currently valid{' '}
                  {layer === 'sigmet'
                    ? `advisories · ${active.filter((f) => !f.geometry).length} unlocated`
                    : 'stations'}
                  {item.product?.expires_at_ms
                    ? ` · layer expires ${utc(item.product.expires_at_ms)}`
                    : ''}
                </p>
                {reports?.length ? (
                  <ul aria-label={`${layer.toUpperCase()} station reports`}>
                    {reports.map((station) => (
                      <StationReport
                        key={station.id}
                        station={station}
                        now={view.now}
                      />
                    ))}
                  </ul>
                ) : null}
                {layer === 'sigmet' && (
                  <ul aria-label="SIGMET bulletin summaries">
                    {(active as AviationAdvisory[])
                      .slice(0, 3)
                      .map((advisory) => (
                        <AdvisoryReport key={advisory.id} advisory={advisory} />
                      ))}
                  </ul>
                )}
              </>
            )}
            {item.product?.attribution?.map((a) => (
              <p key={a.url}>
                Data by{' '}
                <a href={a.url} target="_blank" rel="noopener noreferrer">
                  {a.label}
                </a>
              </p>
            ))}
          </div>
        );
      })}
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
