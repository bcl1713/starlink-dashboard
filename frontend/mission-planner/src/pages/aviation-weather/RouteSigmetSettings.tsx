import { useState } from 'react';
import { Switch } from '@/components/ui/switch';
import {
  useRouteSigmets,
  useSetSigmetAcknowledgement,
} from '@/hooks/api/useRouteSigmets';
import {
  activeFeatures,
  type AviationAdvisory,
} from '@/services/aviation-features';
import {
  RouteSigmetHttpError,
  type RouteSigmetEntry,
} from '@/services/route-sigmets';
import { AviationReport } from './AviationReport';
import { sigmetReportLabel } from './sigmet-report-label';
import './AviationWeather.css';

const utc = (value: number) =>
  new Date(value).toISOString().replace(/Z$/, ' UTC');
function label(report: AviationAdvisory) {
  const p = report.properties;
  return `${sigmetReportLabel([report])} · ${p.phenomenon ?? 'Unknown phenomenon'}`;
}
function routePosition(entry: RouteSigmetEntry) {
  return entry.spans.reduce(
    (first, span) => Math.min(first, span.segment_index + span.start_fraction),
    Infinity
  );
}

/** Configuration borrows source reports only; no map or drawing owner mounts here. */
export function RouteSigmetSettings({
  enabled,
  intersectingOnly,
  disabled,
  onFilterChange,
}: {
  enabled: boolean;
  intersectingOnly: boolean;
  disabled: boolean;
  onFilterChange: (enabled: boolean) => void;
}) {
  const view = useRouteSigmets();
  const mutation = useSetSigmetAcknowledgement();
  const [feedback, setFeedback] = useState<{
    error: boolean;
    text: string;
  } | null>(null);
  const snapshot = enabled ? view.snapshot : null;
  const collection = enabled && view.available ? view.collection : null;
  const active = collection
    ? (activeFeatures(collection, 'sigmet', view.nowMs) as AviationAdvisory[])
    : [];
  const reports = new Map(active.map((report) => [report.id, report]));
  const entries =
    snapshot?.entries
      .slice()
      .sort(
        (a, b) =>
          routePosition(a) - routePosition(b) ||
          a.bulletin_key.localeCompare(b.bulletin_key)
      ) ?? [];
  const matched = new Set(entries.flatMap((entry) => entry.feature_ids));
  const unknownIds = new Set([
    ...(snapshot?.unresolved.map((item) => item.feature_id) ?? []),
    ...active.filter((report) => !report.geometry).map((report) => report.id),
  ]);
  const unknown = active.filter(
    (report) => unknownIds.has(report.id) && !matched.has(report.id)
  );
  const future =
    collection?.features.filter(
      (report): report is AviationAdvisory =>
        'cancelled' in report.properties &&
        !report.properties.cancelled &&
        !matched.has(report.id) &&
        view.nowMs < report.properties.valid_from_ms &&
        view.nowMs < report.properties.expires_at_ms
    ) ?? [];
  const other = active.filter(
    (report) => !matched.has(report.id) && !unknownIds.has(report.id)
  );
  const reportDetails = (report: AviationAdvisory) => (
    <details key={report.id}>
      <summary>Full report · {label(report)}</summary>
      <AviationReport feature={report} now={view.nowMs} />
    </details>
  );
  function changeNotice(entry: RouteSigmetEntry, bulletinLabel: string) {
    if (!snapshot?.context) return;
    setFeedback(null);
    mutation.mutate(
      {
        context_key: snapshot.context.context_key,
        notice_key: entry.notice_key,
        semantic_digest: entry.semantic_digest,
        acknowledged: !entry.acknowledged,
      },
      {
        onSuccess: () =>
          setFeedback({
            error: false,
            text: `Advisory state saved · ${bulletinLabel}`,
          }),
        onError: (error) =>
          setFeedback({
            error: true,
            text:
              error instanceof RouteSigmetHttpError && error.status === 409
                ? `Advisory changed · refreshing current reports. Review before trying again · ${bulletinLabel}`
                : `Could not save advisory state · ${bulletinLabel}. Its confirmed state is unchanged; try again.`,
          }),
      }
    );
  }
  return (
    <div className="route-sigmet-settings">
      <label className="flex min-h-11 items-center justify-between gap-4 text-sm font-medium">
        Intersecting route only
        <Switch
          aria-label="Intersecting route only"
          checked={intersectingOnly}
          disabled={disabled || !enabled}
          onChange={(event) => onFilterChange(event.target.checked)}
        />
      </label>
      <p className="text-xs text-muted-foreground">
        Geographic intersection · Altitude and passage-time match not evaluated.
        Weather uses actual UTC, including simulation routes.
      </p>
      <p className="text-xs text-muted-foreground">
        Coverage is unknown or partial. Missing reports mean unknown weather; no
        matching reports do not establish a clear route.
      </p>
      {enabled && (
        <>
          <p>
            {snapshot?.context
              ? `${snapshot.context.route_name || 'Unnamed route'} · ${snapshot.context.source === 'simulation' ? 'Simulation route' : 'Ordinary route'}`
              : 'Route unavailable'}
          </p>
          <p role="status">
            Route SIGMET status: {snapshot?.status ?? 'unavailable'}
            {snapshot?.reason ? ` · ${snapshot.reason}` : ''}
            {view.error
              ? ' · Reports unavailable or refresh failed; original validity still applies.'
              : ''}
          </p>
          {snapshot && !snapshot.complete && (
            <p>
              Route evaluation incomplete; some intersections remain unknown.
            </p>
          )}
          {snapshot?.status === 'no-route' && (
            <p>No usable route. Intersecting-only shows no polygons.</p>
          )}
          {entries.length > 0 ? (
            <ol aria-label="Matching route SIGMET bulletins">
              {entries.map((entry) => {
                const boundReports = entry.feature_ids
                  .map((id) => reports.get(id))
                  .filter((report): report is AviationAdvisory => !!report);
                const report = boundReports[0];
                const bulletinLabel = `${sigmetReportLabel(boundReports)}${report ? ` · ${report.properties.phenomenon ?? 'Unknown phenomenon'}` : ''} · ${entry.bulletin_key.slice(0, 8)}`;
                const segments = [
                  ...new Set(entry.spans.map((span) => span.segment_index + 1)),
                ].sort((a, b) => a - b);
                return (
                  <li key={entry.notice_key}>
                    <p>
                      <strong>{bulletinLabel}</strong> ·{' '}
                      {entry.acknowledged ? 'Acknowledged' : 'Pending'}
                    </p>
                    <p>
                      Route segment{segments.length === 1 ? '' : 's'}{' '}
                      {segments.join(', ')}
                      {entry.identity_uncertain
                        ? ' · Bulletin identity uncertain'
                        : ''}
                      {entry.feature_ids.some((id) => unknownIds.has(id))
                        ? ' · Some route intersections unknown'
                        : ''}
                    </p>
                    {boundReports.length > 0 ? (
                      boundReports.map(reportDetails)
                    ) : (
                      <p>
                        Original report unavailable; advisory actions are
                        disabled until reports refresh.
                      </p>
                    )}
                    <button
                      type="button"
                      disabled={
                        disabled ||
                        mutation.isPending ||
                        !view.available ||
                        !report ||
                        !snapshot?.context
                      }
                      aria-label={`${entry.acknowledged ? 'Show again' : 'Clear advisory'} · ${bulletinLabel}`}
                      onClick={() => changeNotice(entry, bulletinLabel)}
                    >
                      {entry.acknowledged ? 'Show again' : 'Clear advisory'}
                    </button>
                  </li>
                );
              })}
            </ol>
          ) : (
            <p>No current matching route bulletins returned.</p>
          )}
          {unknown.length > 0 && (
            <section aria-label="Route intersection unknown">
              <h4>Route intersection unknown</h4>
              {unknown.map((report) => (
                <div key={report.id}>
                  <p>
                    {snapshot?.unresolved.find(
                      (item) => item.feature_id === report.id
                    )?.reason ?? (!report.geometry ? 'unlocated' : 'unknown')}
                  </p>
                  {reportDetails(report)}
                </div>
              ))}
            </section>
          )}
          {future.length > 0 && (
            <section aria-label="Future SIGMET reports">
              <h4>Future SIGMET reports</h4>
              <p>Not yet valid; no current route notice.</p>
              {future.map(reportDetails)}
            </section>
          )}
          {other.length > 0 && (
            <section aria-label="Other current SIGMET reports">
              <h4>Other current SIGMET reports</h4>
              <p>No confirmed route intersection returned for these reports.</p>
              {other.map(reportDetails)}
            </section>
          )}
          {collection && (
            <div className="route-sigmet-source">
              <p>
                Source {collection.source_id.toUpperCase()} · retrieved{' '}
                {utc(collection.retrieved_at_ms)}
              </p>
              <p>
                Feed coverage {collection.feed_completeness} ·{' '}
                {snapshot?.omitted_features ?? collection.omitted_features}{' '}
                omitted
              </p>
              {snapshot?.sigmet_product.attribution.map((item) => (
                <a
                  key={item.url}
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {item.label}
                </a>
              ))}
            </div>
          )}
          <div aria-live="polite">
            {mutation.isPending && <p role="status">Saving advisory state…</p>}
            {feedback && (
              <p role={feedback.error ? 'alert' : 'status'}>{feedback.text}</p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
