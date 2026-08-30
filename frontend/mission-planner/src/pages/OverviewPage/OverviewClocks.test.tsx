import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { createDefaultOverviewPreferences } from './preferences';
import { OverviewClocks } from './OverviewClocks';

describe('OverviewClocks', () => {
  it('renders UTC directly and controls additional clocks accessibly', () => {
    const onExpandedChange = vi.fn();
    const preferences = createDefaultOverviewPreferences();
    const { container } = render(
      <OverviewClocks
        clocks={preferences.clocks}
        expanded={false}
        now={new Date('2026-01-02T03:04:05Z')}
        onExpandedChange={onExpandedChange}
      />
    );

    const utc = screen.getByText('UTC (Zulu)').closest('article');
    expect(utc).not.toBeNull();
    expect(within(utc as HTMLElement).getByText('03:04:05')).toBeVisible();
    expect(
      within(utc as HTMLElement).getByLabelText(
        'UTC (Zulu): 03:04:05, UTC (UTC+00:00)'
      )
    ).toHaveAttribute('dateTime', '2026-01-02T03:04:05.000Z');
    expect(screen.queryByText('Washington DC')).not.toBeVisible();
    const button = screen.getByRole('button', { name: 'Additional clocks' });
    expect(button).toHaveAttribute('aria-expanded', 'false');
    expect(
      document.getElementById(button.getAttribute('aria-controls') ?? '')
    ).not.toBeNull();
    fireEvent.click(button);
    expect(onExpandedChange).toHaveBeenCalledWith(true);
    expect(container.querySelector('[aria-live]')).toBeNull();
  });

  it('renders expanded clocks, unavailable states, and hostile labels as text', () => {
    render(
      <OverviewClocks
        clocks={[
          { id: 'utc', timeZone: 'UTC', label: 'UTC (Zulu)' },
          { id: 'bad', timeZone: 'No/Such', label: '<img src=x onerror=1>' },
        ]}
        expanded
        now={new Date('2026-01-02T03:04:05Z')}
        onExpandedChange={() => {}}
      />
    );

    expect(screen.getByText('<img src=x onerror=1>')).toBeVisible();
    expect(screen.getByText('Time unavailable')).toBeVisible();
    expect(document.querySelector('img')).toBeNull();
  });
});
