import { useState, type CSSProperties } from 'react';
import type { SigmetPresentation } from './route-sigmet-presentation';
import { SigmetAttentionCard } from './SigmetAttentionCard';
import './AviationWeather.css';
export function RouteSigmetNotices({
  presentation,
  focusedNoticeKey,
}: {
  presentation: SigmetPresentation;
  focusedNoticeKey?: string | null;
}) {
  const items = presentation.attentionItems;
  const [page, setPage] = useState(0);
  const [lastFocus, setLastFocus] = useState<string | null | undefined>(
    undefined
  );
  let current = Math.min(page, Math.max(0, Math.ceil(items.length / 3) - 1));
  if (focusedNoticeKey !== lastFocus) {
    setLastFocus(focusedNoticeKey);
    const index = items.findIndex(
      (i) => i.entry.notice_key === focusedNoticeKey
    );
    if (index >= 0) {
      current = Math.floor(index / 3);
      setPage(current);
    }
  }
  if (!items.length) return null;
  const pages = Math.ceil(items.length / 3);
  return (
    <section
      className="route-sigmet-notices"
      aria-label="Route SIGMET advisories"
    >
      <p
        className="sigmet-attention-count sigmet-attention-pulse"
        style={{ '--sigmet-color': items[0].color } as CSSProperties}
      >
        SIGMETS: {items.length}
      </p>
      <div aria-live="polite" aria-relevant="additions removals">
        {items.slice(current * 3, current * 3 + 3).map((item) => (
          <SigmetAttentionCard key={item.entry.notice_key} item={item} />
        ))}
      </div>
      {pages > 1 && (
        <nav aria-label="SIGMET attention navigation">
          <button
            type="button"
            disabled={current === 0}
            onClick={() => setPage(current - 1)}
          >
            Previous
          </button>
          <button
            type="button"
            disabled={current === pages - 1}
            onClick={() => setPage(current + 1)}
          >
            Next
          </button>
        </nav>
      )}
    </section>
  );
}
