import { useState } from 'react';
import type { OverviewAdvisoryState } from './overview-advisories';
import './OverviewPopAdvisories.css';

/** Concise shared cues; dismissing a coverage notice never acknowledges events. */
export function OverviewPopAdvisories({
  state,
}: {
  state: OverviewAdvisoryState;
}) {
  const [dismissed, setDismissed] = useState(false);
  // A dismissal covers one continuous failure, including stale/unavailable
  // changes. Healthy coverage rearms a later failure without polling reopening it.
  if (!state.notice && dismissed) setDismissed(false);
  const notice = state.notice && !dismissed ? state.notice : null;
  if (!state.items.length && !notice) return null;
  return (
    <section
      role="status"
      tabIndex={0}
      className="overview-transport-advisories"
      aria-label="Transport Advisories"
    >
      {state.items.map((item) => (
        <div key={item.id} className="overview-transport-advisory">
          <strong>{item.title}</strong>
          <span>{item.detail}</span>
        </div>
      ))}
      {notice && (
        <div className="overview-transport-advisories__notice">
          <p>{notice}</p>
          <button
            type="button"
            aria-label="Dismiss transport advisory notice"
            onClick={() => setDismissed(true)}
          >
            ×
          </button>
        </div>
      )}
    </section>
  );
}
