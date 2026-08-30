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

  it('locates, synthesizes, and deduplicates UTC without mutating clocks', () => {
    const now = new Date('2026-01-02T03:04:05Z');
    const misordered = [
      { id: 'tokyo', timeZone: 'Asia/Tokyo', label: 'Tokyo' },
      { id: 'utc', timeZone: 'UTC', label: 'Zulu Direct' },
      { id: 'etc', timeZone: 'Etc/UTC', label: 'Zulu Duplicate' },
    ];
    const original = JSON.stringify(misordered);
    const { rerender } = render(
      <OverviewClocks
        clocks={misordered}
        expanded
        now={now}
        onExpandedChange={() => {}}
      />
    );

    expect(screen.getAllByRole('article')[0]).toHaveTextContent('Zulu Direct');
    expect(screen.queryByText('Zulu Duplicate')).toBeNull();
    expect(JSON.stringify(misordered)).toBe(original);

    rerender(
      <OverviewClocks
        clocks={[{ id: 'tokyo', timeZone: 'Asia/Tokyo', label: 'Tokyo' }]}
        expanded
        now={now}
        onExpandedChange={() => {}}
      />
    );

    expect(screen.getAllByRole('article')[0]).toHaveTextContent('UTC (Zulu)');
    expect(screen.getByText('Tokyo')).toBeVisible();
  });

  it('uses guarded canonical UTC ahead of hostile ids and keeps fake UTC additional', () => {
    const clocks = [
      { id: 'utc', timeZone: 'Asia/Tokyo', label: 'Fake UTC' },
      { id: 'real', timeZone: 'UTC', label: 'Real UTC' },
      { id: 'alias', timeZone: 'Etc/UTC', label: 'Alias UTC' },
      { id: 'nyc', timeZone: 'America/New_York', label: 'New York' },
    ];
    const original = JSON.stringify(clocks);

    render(
      <OverviewClocks
        clocks={clocks}
        expanded
        now={new Date('2026-01-02T03:04:05Z')}
        onExpandedChange={() => {}}
      />
    );

    expect(screen.getAllByRole('article')[0]).toHaveTextContent('Real UTC');
    expect(screen.getByText('Fake UTC')).toBeVisible();
    expect(screen.queryByText('Alias UTC')).toBeNull();
    expect(screen.getByText('New York')).toBeVisible();
    expect(JSON.stringify(clocks)).toBe(original);
  });

  it('canonicalizes each clock once per render before partitioning', () => {
    const OriginalDateTimeFormat = Intl.DateTimeFormat;
    let canonicalChecks = 0;
    const spy = vi.spyOn(Intl, 'DateTimeFormat').mockImplementation(function (
      ...args: ConstructorParameters<typeof Intl.DateTimeFormat>
    ) {
      const [, options] = args;
      if (options && typeof options === 'object' && !('hour' in options)) {
        canonicalChecks += 1;
      }
      return new OriginalDateTimeFormat(...args);
    } as never);

    render(
      <OverviewClocks
        clocks={[
          { id: 'utc', timeZone: 'UTC', label: 'UTC (Zulu)' },
          { id: 'tokyo', timeZone: 'Asia/Tokyo', label: 'Tokyo' },
          { id: 'nyc', timeZone: 'America/New_York', label: 'New York' },
        ]}
        expanded
        now={new Date('2026-01-02T03:04:05Z')}
        onExpandedChange={() => {}}
      />
    );

    expect(canonicalChecks).toBe(3);
    spy.mockRestore();
  });
});
