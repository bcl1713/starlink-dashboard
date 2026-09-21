/** @vitest-environment jsdom */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { OperationalClockList } from './OperationalClockList';
afterEach(() => {
  cleanup();
});
describe('OperationalClockList', () => {
  it('renders every configured operational clock', () => {
    render(
      <OperationalClockList
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
      />
    );
    expect(
      screen.getAllByRole('region', {
        name: /operational clock$/i,
      })
    ).toHaveLength(4);
    expect(screen.getByText('Zulu / UTC')).not.toBeNull();
    expect(screen.getByText('Washington, DC')).not.toBeNull();
    expect(screen.getByText('Omaha, NE')).not.toBeNull();
    expect(screen.getByText('Tokyo, JP')).not.toBeNull();
  });
});
