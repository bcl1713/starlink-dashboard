import type { OverviewAdvisoryState } from './overview-advisories';
import './OverviewPopAdvisories.css';

/** Concise shared transport cues; details and acknowledgment stay in Operator. */
export function OverviewPopAdvisories({
  state,
}: {
  state: OverviewAdvisoryState;
}) {
  if (!state.items.length && !state.notice) return null;
  return (
    <section
      role="status"
      className="overview-transport-advisories"
      aria-label="Transport Advisories"
    >
      {state.items.map((item) => (
        <div key={item.id} className="overview-transport-advisory">
          <strong>{item.title}</strong>
          <span>{item.detail}</span>
        </div>
      ))}
      {state.notice && (
        <p className="overview-transport-advisories__notice">{state.notice}</p>
      )}
    </section>
  );
}
