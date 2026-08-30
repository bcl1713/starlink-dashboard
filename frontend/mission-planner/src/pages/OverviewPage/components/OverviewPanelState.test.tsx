import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { OverviewPanelState } from './OverviewPanelState';
import { slot } from './metric-panel-test-fixtures';

describe('OverviewPanelState', () => {
  it('renders one labelled region heading and retained stale data with retry', () => {
    const retry = vi.fn().mockRejectedValue(new Error('ignored'));
    const stale = {
      ...slot({ value: 1 }, 'stale'),
      freshness: 'stale',
    } as const;

    render(
      <OverviewPanelState
        title="Network Latency"
        slot={stale}
        retryPending={false}
        onRetry={retry}
        headingAs="h3"
      >
        {(data) => <p>Value {data.value}</p>}
      </OverviewPanelState>
    );

    expect(
      screen.getByRole('region', { name: 'Network Latency' })
    ).toBeInTheDocument();
    expect(
      screen.getAllByRole('heading', { name: 'Network Latency' })
    ).toHaveLength(1);
    expect(screen.getByText('Stale')).toBeVisible();
    expect(screen.getByText('Value 1')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(retry).toHaveBeenCalledTimes(1);
  });

  it('keeps retry disabled by independent retryPending', () => {
    render(
      <OverviewPanelState
        title="Panel"
        slot={slot(undefined, 'error')}
        retryPending
        onRetry={vi.fn()}
      >
        {() => <p>hidden</p>}
      </OverviewPanelState>
    );

    expect(screen.getByRole('button', { name: 'Retry' })).toBeDisabled();
    expect(screen.queryByText('hidden')).not.toBeInTheDocument();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });
});
