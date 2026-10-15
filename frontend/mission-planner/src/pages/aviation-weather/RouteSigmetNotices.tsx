import type { AviationAdvisory } from '@/services/aviation-features';
import type { SigmetPresentation } from './route-sigmet-presentation';
import './AviationWeather.css';
const utc = (value: number) =>
  new Date(value).toISOString().replace(/Z$/, ' UTC');
export function RouteSigmetNotices({
  presentation,
}: {
  presentation: SigmetPresentation;
}) {
  return (
    <section
      className="route-sigmet-notices overview-weather-status"
      aria-label="Route SIGMET advisories"
    >
      <p>
        {presentation.routeLabel || 'Selected route'} ·{' '}
        {presentation.statusText}
      </p>
      <p>
        {presentation.routeLabel
          ? `${presentation.pendingCount} pending route advisories${presentation.pendingCount > 3 ? ` · ${presentation.pendingCount - 3} additional in Configuration` : ''}`
          : 'Pending route advisories unavailable'}
      </p>
      {presentation.unknownCount > 0 && (
        <p>
          {presentation.unknownCount} reports with route intersection unknown
        </p>
      )}
      {presentation.highlightUnavailable && (
        <p>Highlight unavailable · advisory details remain below</p>
      )}
      <div aria-live="polite" aria-relevant="additions text">
        {presentation.notices.map((notice) => {
          const p = (notice.reports[0] as AviationAdvisory).properties;
          const segments = [
            ...new Set(
              notice.entry.spans.map((span) => span.segment_index + 1)
            ),
          ].sort((a, b) => a - b);
          return (
            <article
              key={notice.entry.notice_key}
              className="route-sigmet-notice"
              style={{ borderColor: notice.color }}
              aria-label={`Route advisory · ${notice.label}`}
            >
              <h3>Route advisory · {notice.label}</h3>
              <p>
                {p.phenomenon ?? 'Unknown phenomenon'} ·{' '}
                {p.severity ?? 'Unknown severity'}
              </p>
              <p>
                Route segment{segments.length === 1 ? '' : 's'}{' '}
                {segments.join(', ') || 'unknown'}
                {notice.intersectionUnknown
                  ? ' · Some route intersections unknown'
                  : ''}
              </p>
              <p>
                {p.vertical.unit === 'unknown' ||
                (p.vertical.lower === null && p.vertical.upper === null)
                  ? 'Vertical bounds unknown'
                  : `Reported vertical bounds ${p.vertical.lower ?? 'unknown'}–${p.vertical.upper ?? 'unknown'} ${p.vertical.unit} ${p.vertical.reference}`}{' '}
                · FIR {p.fir ?? 'unknown'}
              </p>
              <p>
                Valid {utc(notice.entry.valid_from_ms)} –{' '}
                {utc(notice.entry.expires_at_ms)}
              </p>
              {notice.entry.identity_uncertain && (
                <p>Bulletin identity uncertain</p>
              )}
              <p>
                Geographic intersection · Altitude and passage-time match not
                evaluated
              </p>
            </article>
          );
        })}
      </div>
      <p className="aviation-coverage-note">
        Coverage unknown or partial · missing reports mean unknown weather
      </p>
    </section>
  );
}
