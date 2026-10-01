import type { ArrivalPanelState } from './overview-arrival';
import './OverviewArrivalPanel.css';

export function OverviewArrivalPanel({ state }: { state: ArrivalPanelState }) {
  return (
    <aside className="overview-arrival" aria-label="Departure and arrival">
      {state.message ? (
        <p className="overview-arrival__message">{state.message}</p>
      ) : (
        <div className="overview-arrival__sections">
          {state.sections.map((section) => (
            <section
              className="overview-arrival__section"
              key={section.label}
              aria-label={section.label}
            >
              <h2>
                {section.label}
                {section.name ? ` · ${section.name}` : ''}
              </h2>
              {section.timing ? (
                <>
                  <p
                    className={`overview-arrival__countdown${section.timing.late ? ' overview-arrival__countdown--late' : ''}`}
                  >
                    {section.timing.countdown}
                  </p>
                  <p className="overview-arrival__utc">
                    {section.label === 'SCHEDULED DEPARTURE'
                      ? 'SCHEDULED '
                      : 'ETA '}
                    <time
                      dateTime={section.timing.timestamp}
                      aria-label={section.timing.timestamp}
                    >
                      {section.timing.utc}
                    </time>
                    {section.timing.anticipated ? ' · anticipated' : ''}
                  </p>
                </>
              ) : section.unavailable ? (
                <p className="overview-arrival__message">
                  {section.unavailable}
                </p>
              ) : null}
            </section>
          ))}
        </div>
      )}
      {state.exception && (
        <p className="overview-arrival__exception" role="status">
          {state.exception}
        </p>
      )}
    </aside>
  );
}
