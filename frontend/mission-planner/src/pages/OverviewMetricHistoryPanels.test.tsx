/** @vitest-environment jsdom */
import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { OverviewHistoryBundle } from '../services/overview-history';
import { OVERVIEW_METRIC_GRAPHS } from './overview-metric-history';
import { OverviewMetricHistoryPanels } from './OverviewMetricHistoryPanels';

vi.mock('./OverviewMetricHistoryPanel', () => ({
  OverviewMetricHistoryPanel: ({
    descriptor,
    history,
  }: {
    descriptor: { label: string; metric: string };
    history?: OverviewHistoryBundle;
  }) => (
    <section aria-label={`${descriptor.label} history`}>
      <h3>{descriptor.label}</h3>
      <span>{history?.series?.[descriptor.metric]?.[0]?.[1]}</span>
    </section>
  ),
}));
afterEach(cleanup);

describe('OverviewMetricHistoryPanels', () => {
  it('projects one shared history result into five separately named panels without fetching', () => {
    const history: OverviewHistoryBundle = {
      window_seconds: 300,
      start_timestamp_seconds: 0,
      end_timestamp_seconds: 300,
      step_seconds: 5,
      series: Object.fromEntries(
        OVERVIEW_METRIC_GRAPHS.map((graph, index) => [
          graph.metric,
          [[300, index + 1]],
        ])
      ),
    };
    render(
      <OverviewMetricHistoryPanels
        history={history}
        error={false}
        selectedWindowSeconds={300}
        nowMs={300_000}
      />
    );
    const region = screen.getByLabelText('Overview metric history');
    expect(region.querySelectorAll('[data-metric-panel]')).toHaveLength(5);
    OVERVIEW_METRIC_GRAPHS.forEach((graph, index) => {
      const panel = within(region).getByRole('region', {
        name: `${graph.label} history`,
      });
      expect(
        within(panel).getByRole('heading', { name: graph.label })
      ).toBeTruthy();
      expect(within(panel).getByText(String(index + 1))).toBeTruthy();
    });
  });
});
