import { useState, type CSSProperties } from 'react';
import type { SigmetPresentation } from './route-sigmet-presentation';
import { SigmetAttentionCard } from './SigmetAttentionCard';
import './AviationWeather.css';
export function RouteSigmetNotices({
  presentation,
  page: controlledPage,
  onPageChange,
}: {
  presentation: SigmetPresentation;
  page?: number;
  onPageChange?: (page: number) => void;
}) {
  const items = presentation.attentionItems;
  const [localPage, setLocalPage] = useState(0);
  const page = controlledPage ?? localPage;
  const setPage = onPageChange ?? setLocalPage;
  const current = Math.min(page, Math.max(0, Math.ceil(items.length / 3) - 1));
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
