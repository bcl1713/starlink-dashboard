import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { MetricHistoryDisclosure } from './MetricHistoryDisclosure';
import type { TimeSeriesDefinition, TimeSeriesRow } from './metric-panel-types';

const series: readonly TimeSeriesDefinition[] = [
  {
    key: 'latency',
    label: 'Latency',
    color: '#1769aa',
    unit: 'ms',
    display: 'signed',
  },
];

describe('MetricHistoryDisclosure', () => {
  it('starts closed and renders the chronological latest 300 rows when opened', () => {
    const rows: TimeSeriesRow[] = Array.from({ length: 301 }, (_, index) => ({
      timestamp: `2026-08-29T12:${String(index % 60).padStart(2, '0')}:00Z`,
      epochSeconds: index,
      values: [index],
    }));

    render(
      <MetricHistoryDisclosure
        rows={rows}
        series={series}
        caption="Latency history"
      />
    );

    const button = screen.getByRole('button', { name: 'History' });
    expect(button).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('table')).not.toBeInTheDocument();

    fireEvent.click(button);

    expect(button).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText('Latest 300 of 301 samples')).toBeVisible();
    const scroller = screen.getByRole('region', {
      name: 'Metric history table',
    });
    expect(scroller).toHaveClass('overflow-x-auto');
    expect(scroller).toHaveAttribute('tabIndex', '0');
    expect(screen.getAllByRole('row')).toHaveLength(301);
    expect(screen.queryByText('0.0 ms')).not.toBeInTheDocument();
    expect(screen.getByText('300.0 ms')).toBeVisible();
  });

  it('does not add keyboard focus when the table is not truncated', () => {
    render(
      <MetricHistoryDisclosure rows={[]} series={series} caption="History" />
    );

    fireEvent.click(screen.getByRole('button', { name: 'History' }));

    expect(
      screen.getByRole('region', { name: 'Metric history table' })
    ).not.toHaveAttribute('tabIndex');
  });
});
