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
  type SelectedSigmetEntry,
} from '@/services/route-sigmets';
import { AviationReport } from './AviationReport';
import { sigmetReportLabel } from './sigmet-report-label';
import './AviationWeather.css';
const position = (e: RouteSigmetEntry | SelectedSigmetEntry) =>
  'spans' in e
    ? e.spans.reduce(
        (n, s) => Math.min(n, s.segment_index + s.start_fraction),
        Infinity
      )
    : Infinity;
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
  const view = useRouteSigmets(),
    mutation = useSetSigmetAcknowledgement();
  const [feedback, setFeedback] = useState<{
    error: boolean;
    text: string;
  } | null>(null);
  const snapshot = enabled ? view.snapshot : null;
  const collection = enabled && view.available ? view.collection : null;
  const active = collection
    ? (activeFeatures(collection, 'sigmet', view.nowMs) as AviationAdvisory[])
    : [];
  const reports = new Map(active.map((r) => [r.id, r]));
  const entries = [
    ...(snapshot?.entries ?? []),
    ...(snapshot?.selected_entries ?? []),
  ]
    .filter(
      (e) => e.valid_from_ms <= view.nowMs && view.nowMs < e.expires_at_ms
    )
    .sort(
      (a, b) =>
        position(a) - position(b) ||
        a.bulletin_key.localeCompare(b.bulletin_key)
    );
  function change(entry: SelectedSigmetEntry, label: string) {
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
            text: `Advisory state saved · ${label}`,
          }),
        onError: (error) =>
          setFeedback({
            error: true,
            text:
              error instanceof RouteSigmetHttpError && error.status === 409
                ? `Advisory changed · refreshing current reports. Review before trying again · ${label}`
                : `Could not save advisory state · ${label}. Its confirmed state is unchanged; try again.`,
          }),
      }
    );
  }
  const row = (entry: RouteSigmetEntry | SelectedSigmetEntry) => {
    const bound = entry.feature_ids
      .map((id) => reports.get(id))
      .filter((r): r is AviationAdvisory => !!r);
    const label = bound.length
      ? sigmetReportLabel(bound)
      : `SIGMET ${entry.bulletin_key.slice(0, 8)} · report unavailable`;
    return (
      <li key={entry.notice_key} className="sigmet-settings-row">
        <div className="sigmet-settings-summary">
          <strong>{label}</strong>
          <span>
            {bound[0]?.properties.phenomenon ?? 'Unknown hazard'} ·{' '}
            {bound[0]?.properties.severity ?? 'Unknown severity'}
          </span>
          <span>{'spans' in entry ? 'Intersecting' : 'Selected'}</span>
          <button
            type="button"
            aria-label={`${entry.acknowledged ? 'Show again' : 'Clear advisory'} · ${label}`}
            disabled={
              disabled ||
              mutation.isPending ||
              !view.available ||
              !bound.length ||
              !snapshot?.context
            }
            onClick={() => change(entry, label)}
          >
            {entry.acknowledged ? 'Show again' : 'Acknowledge'}
          </button>
        </div>
        <details>
          <summary>Full report · {label}</summary>
          {bound.length ? (
            bound.map((r) => (
              <AviationReport key={r.id} feature={r} now={view.nowMs} />
            ))
          ) : (
            <p>
              Original report unavailable; advisory actions are disabled until
              reports refresh.
            </p>
          )}
          {'spans' in entry && (
            <p>
              Route segments{' '}
              {[...new Set(entry.spans.map((s) => s.segment_index + 1))].join(
                ', '
              )}
            </p>
          )}
        </details>
      </li>
    );
  };
  return (
    <div className="route-sigmet-settings">
      <label className="flex min-h-11 items-center justify-between gap-4 text-sm font-medium">
        Show intersecting polygons only
        <Switch
          aria-label="Show intersecting polygons only"
          checked={intersectingOnly}
          disabled={disabled || !enabled}
          onChange={(e) => onFilterChange(e.target.checked)}
        />
      </label>
      {enabled && (
        <>
          <section aria-label="Pending SIGMETs">
            <h4>Pending</h4>
            {entries.some((e) => !e.acknowledged) ? (
              <ol aria-label="Matching route SIGMET bulletins">
                {entries.filter((e) => !e.acknowledged).map(row)}
              </ol>
            ) : (
              <p>No pending SIGMETs.</p>
            )}
          </section>
          <details className="sigmet-cleared">
            <summary>Cleared</summary>
            {entries.some((e) => e.acknowledged) ? (
              <ol aria-label="Cleared route SIGMET bulletins">
                {entries.filter((e) => e.acknowledged).map(row)}
              </ol>
            ) : (
              <p>No cleared SIGMETs.</p>
            )}
          </details>
          <details>
            <summary>Diagnostics</summary>
            <p>
              {snapshot?.context
                ? `${snapshot.context.route_name || 'Unnamed route'} · ${snapshot.context.source === 'simulation' ? 'Simulation route' : 'Ordinary route'}`
                : 'Route unavailable'}
            </p>
            <p>
              Route SIGMET status: {snapshot?.status ?? 'unavailable'}
              {snapshot?.reason ? ` · ${snapshot.reason}` : ''}
            </p>
            <p>
              Geographic intersection · Altitude and passage-time match not
              evaluated. Weather uses actual UTC, including simulation routes.
            </p>
            {view.error && (
              <p>
                Reports unavailable or refresh failed; original validity still
                applies.
              </p>
            )}
            {snapshot && !snapshot.complete && (
              <p>
                Route evaluation incomplete; some intersections remain unknown.
              </p>
            )}
            {collection && (
              <p>
                Source {collection.source_id.toUpperCase()} · retrieved{' '}
                {new Date(collection.retrieved_at_ms)
                  .toISOString()
                  .replace(/Z$/, ' UTC')}{' '}
                · Feed coverage {collection.feed_completeness} ·{' '}
                {snapshot?.omitted_features ?? collection.omitted_features}{' '}
                omitted
              </p>
            )}
            {snapshot?.sigmet_product.attribution.map((a) => (
              <a
                key={a.url}
                href={a.url}
                target="_blank"
                rel="noopener noreferrer"
              >
                {a.label}
              </a>
            ))}
          </details>
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
