/** @vitest-environment jsdom */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { OverviewClockPanel } from './OverviewClockPanel';
afterEach(() => {
  cleanup();
});
describe('OverviewClockPanel', () => {
  it('announces that operational clocks are loading', () => {
    render(
      <OverviewClockPanel
        clocks={undefined}
        currentTime={Date.UTC(2026, 0, 2, 0, 5, 6)}
        isError={false}
        isLoading
      />
    );
    expect(screen.getByText('Loading operational clocks...')).not.toBeNull();
  });
  it('announces that operational clocks are unavailable', () => {
    render(
      <OverviewClockPanel
        clocks={undefined}
        currentTime={Date.UTC(2026, 0, 2, 0, 5, 6)}
        isError
        isLoading={false}
      />
    );
    expect(screen.getByRole('alert')).not.toBeNull();
    expect(screen.getByText('Operational clocks unavailable')).not.toBeNull();
  });
  it('renders the saved clock collection after loading', () => {
    render(
      <OverviewClockPanel
        clocks={[
          {
            label: 'Zulu / UTC',
            time_zone: 'UTC',
          },
          {
            label: 'Washington, DC',
            time_zone: 'America/New_York',
          },
          {
            label: 'Omaha, NE',
            time_zone: 'America/Chicago',
          },
          {
            label: 'Tokyo, JP',
            time_zone: 'Asia/Tokyo',
          },
        ]}
        currentTime={Date.UTC(2026, 0, 2, 0, 5, 6)}
        isError={false}
        isLoading={false}
      />
    );
    expect(
      screen.getAllByRole('region', {
        name: /operational clock$/i,
      })
    ).toHaveLength(4);
  });
});
