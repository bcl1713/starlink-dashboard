/** @vitest-environment jsdom */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { popForecast } from '@/test/pop-fixtures';
import type {
  CallContinuityProjection,
  CallContinuityInterval,
} from '@/types/pop';
import { PopForecastPanel } from './PopForecastPanel';
afterEach(cleanup);
it.each([
  ['planned_outage', 'No secure-call transport', 600],
  ['x_fallback', 'Planned X-Band fallback', 0],
  ['advisory', 'alternative available: Ka', 0],
  ['unknown', 'Call continuity unresolved', 0],
] as const)(
  'renders %s without changing physical Starshield',
  (classification, label, seconds) => {
    const forecast = popForecast();
    const continuity: CallContinuityProjection = {
      revision: forecast.revision,
      intervals: [
        {
          start_utc: forecast.transitions[0].window_start_utc,
          end_utc: forecast.transitions[0].window_end_utc,
          classification:
            classification as CallContinuityInterval['classification'],
          transition_ids: [forecast.transitions[0].crossing.id],
          usable_alternatives: classification === 'advisory' ? ['Ka'] : [],
          source_ids: [],
        },
      ],
      planned_communications_outage_seconds: seconds,
      pop_call_outage_seconds: seconds,
      longest_call_outage_seconds: seconds,
    };
    const original = structuredClone(continuity);
    const { container } = render(
      <PopForecastPanel
        forecast={forecast}
        continuity={continuity}
        segments={[
          {
            id: 'physical',
            start_time: forecast.transitions[0].window_start_utc,
            end_time: forecast.transitions[0].window_end_utc,
            status: 'nominal',
            ku_state: 'available',
          },
        ]}
      />
    );
    expect(screen.getAllByText(new RegExp(label)).length).toBeGreaterThan(0);
    expect(container.querySelector('.bg-green-600\\/15')).not.toBeNull();
    expect(container.querySelector('[data-pop-track]')?.textContent).toBe('');
    expect(continuity).toEqual(original);
  }
);
