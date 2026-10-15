import { useState, type CSSProperties } from 'react';
import type { SigmetAttentionItem } from './sigmet-attention';
import {
  useRouteSigmets,
  useSetSigmetAcknowledgement,
} from '@/hooks/api/useRouteSigmets';
import { AviationReport } from './AviationReport';
export function SigmetAttentionCard({
  item,
  onAcknowledged,
}: {
  item: SigmetAttentionItem;
  onAcknowledged?: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const view = useRouteSigmets(),
    mutation = useSetSigmetAcknowledgement();
  const contextKey = view.snapshot?.context?.context_key;
  const p = item.reports[0].properties;
  const segments =
    item.kind === 'intersecting'
      ? [...new Set(item.entry.spans.map((s) => s.segment_index + 1))].sort(
          (a, b) => a - b
        )
      : [];
  return (
    <article
      className="route-sigmet-notice sigmet-attention-pulse"
      style={{ '--sigmet-color': item.color } as CSSProperties}
      aria-label={`SIGMET · ${item.label}`}
    >
      <h3>{item.label}</h3>
      <p>
        {p.phenomenon ?? 'Unknown hazard'} · {p.severity ?? 'Unknown severity'}
      </p>
      <p>
        {item.kind === 'selected'
          ? 'Selected'
          : `Route segment${segments.length === 1 ? '' : 's'} ${segments.join(', ')}`}
      </p>
      <div className="sigmet-attention-actions">
        <details onToggle={(e) => setExpanded(e.currentTarget.open)}>
          <summary>Details</summary>
          {expanded &&
            item.reports.map((r) => (
              <AviationReport key={r.id} feature={r} now={view.nowMs} />
            ))}
        </details>
        <button
          type="button"
          disabled={!contextKey || !view.available || mutation.isPending}
          aria-label={`Acknowledge · ${item.label}`}
          onClick={() => {
            if (contextKey)
              mutation.mutate(
                {
                  context_key: contextKey,
                  notice_key: item.entry.notice_key,
                  semantic_digest: item.entry.semantic_digest,
                  acknowledged: true,
                },
                { onSuccess: onAcknowledged }
              );
          }}
        >
          Acknowledge
        </button>
      </div>
      {mutation.error && <p role="alert">Could not acknowledge. Try again.</p>}
    </article>
  );
}
