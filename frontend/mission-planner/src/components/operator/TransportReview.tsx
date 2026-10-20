import type {
  TransportAssessment,
  TransportReviewData,
} from '@/types/operatorTransport';
import type { OperationalEvent } from '@/types/operatorEvents';
import { revisionUtc } from './revisionUtc';
export function TransportReview({
  review,
  stale,
  error,
  events = [],
}: {
  review?: TransportReviewData | null;
  stale: boolean;
  error: boolean;
  events?: OperationalEvent[];
}) {
  const unknown = stale || error || !review;
  const groups = new Map<
    string,
    { assessment: TransportAssessment; count: number }
  >();
  for (const assessment of review?.assessments ?? []) {
    if (assessment.status === 'no_overlap_found') continue;
    const key = JSON.stringify([
      assessment.decision_id,
      assessment.row_id,
      assessment.subject,
      assessment.report_stage,
      assessment.transport,
      assessment.status,
      assessment.message,
      assessment.event_ids,
      assessment.change_basis,
      assessment.freshness,
    ]);
    const prior = groups.get(key);
    if (prior) prior.count++;
    else groups.set(key, { assessment, count: 1 });
  }
  const stageLabels = {
    intended: 'Intended',
    requested: 'Requested',
    applied: 'Reported Applied',
  };
  return (
    <aside
      aria-label="Transport risk review"
      className="min-w-0 space-y-3 rounded-lg border p-3 [overflow-wrap:anywhere]"
    >
      <h3 className="font-semibold">Communications and modeled restrictions</h3>
      <p>Actual routing unknown.</p>
      {unknown ? (
        <p role="status">
          Review unavailable or stale. Last context may be shown; decisions can
          still be recorded.
        </p>
      ) : (
        <p>
          Model coverage: {review.coverage} · {revisionUtc(review.as_of)} · UTC
        </p>
      )}
      {!unknown &&
        review.activities.some(
          (a) =>
            a.kind !== 'conference' &&
            (a.ongoing ||
              (a.start_at &&
                Date.parse(a.start_at) <= Date.parse(review.as_of) &&
                (!a.end_at || Date.parse(a.end_at) > Date.parse(review.as_of))))
        ) && (
          <p className="rounded border p-2">
            Customer communications are active; transport changes may affect
            them.
          </p>
        )}
      <p className="text-sm">
        Advisory only. Saved assessments refer to saved decision versions;
        drafts may differ.
      </p>
      {review?.activities.map((a, i) => (
        <div key={`${a.record_id}:${a.kind}:${i}`} className="border-t pt-2">
          <p>
            {a.kind === 'preparation'
              ? 'Prepare'
              : a.kind === 'connected'
                ? 'Connected customer'
                : a.kind === 'conference'
                  ? 'Established conference'
                  : 'Customer call'}
            : {a.title}
          </p>
          <p className="text-sm">
            {revisionUtc(a.start_at)} – {revisionUtc(a.end_at)} ·{' '}
            {a.basis.replaceAll('_', ' ')}
          </p>
        </div>
      ))}
      {events
        .filter(
          (e) => e.active && ['restriction', 'pop_advisory'].includes(e.kind)
        )
        .map((e) => (
          <p key={e.event_id} className="border-t pt-2">
            {e.title} · {revisionUtc(e.due_at)} – {revisionUtc(e.end_at)} ·{' '}
            {e.time_basis === 'live_route_eta'
              ? 'Live route ETA'
              : e.time_basis === 'planned_utc'
                ? 'Planned UTC'
                : e.kind === 'pop_advisory'
                  ? 'PoP advisory'
                  : 'Timing unknown'}
          </p>
        ))}
      {!unknown &&
        [...groups].map(([key, { assessment: a, count }]) => (
          <div key={key} className="rounded border p-2">
            <p>
              {a.service}
              {a.report_stage !== 'unknown'
                ? ` · ${stageLabels[a.report_stage]}${a.transport ? ` ${a.transport}` : ''}`
                : ''}
              : {a.message}
            </p>
            {count > 1 && (
              <p className="text-sm text-muted-foreground">
                {count} communications contexts
              </p>
            )}
          </div>
        ))}
    </aside>
  );
}
