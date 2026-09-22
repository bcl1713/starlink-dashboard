/** @vitest-environment jsdom */

import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import type { OverviewUpcomingPoi } from '@/services/overview-upcoming-pois';
import { UpcomingPoisPanel } from './UpcomingPoisPanel';

const now = new Date('2026-09-22T12:00:00.000Z');

function poi(index: number): OverviewUpcomingPoi {
  return {
    poi_id: `poi-${index}`,
    name: `POI ${index}`,
    kind: 'x_band_transition',
    latitude: 41.2,
    longitude: -95.9,
    expected_arrival_time: '2026-09-22T11:00:00.000Z',
    eta_seconds: index * 60,
    estimated_arrival_time: new Date(
      now.valueOf() + index * 60_000
    ).toISOString(),
    eta_type: 'estimated',
    upcoming: true,
    map_retained: true,
  };
}

afterEach(() => {
  cleanup();
});

describe('UpcomingPoisPanel', () => {
  it('labels a missing or invalid estimated ETA as ETA unavailable', () => {
    const unavailablePoi = {
      ...poi(1),
      estimated_arrival_time: null,
      eta_seconds: null,
    };

    render(
      <UpcomingPoisPanel
        state="available"
        pois={[unavailablePoi]}
        currentTime={now}
      />
    );

    expect(screen.getByText('ETA unavailable')).not.toBeNull();
  });

  it('renders human-readable type and UTC timing provenance for dynamic arrivals', () => {
    const anticipatedPoi = {
      ...poi(1),
      kind: 'ka_coverage_entry' as const,
      eta_type: 'anticipated' as const,
      estimated_arrival_time: '2026-09-22T12:01:00.000Z',
    };

    render(
      <UpcomingPoisPanel
        state="available"
        pois={[anticipatedPoi]}
        currentTime={now}
      />
    );

    expect(screen.getByRole('columnheader', { name: 'Type' })).not.toBeNull();
    expect(screen.getByText('Ka coverage entry')).not.toBeNull();
    expect(
      screen.getByText('2026-09-22 12:01 UTC · anticipated')
    ).not.toBeNull();
  });

  it('has a headerless swatch column, no scrolling, and a five-row maximum', () => {
    render(
      <UpcomingPoisPanel
        state="available"
        pois={Array.from({ length: 6 }, (_, index) => poi(index + 1))}
        currentTime={now}
      />
    );

    expect(screen.getAllByRole('row')).toHaveLength(6);
    expect(screen.queryByRole('columnheader', { name: /urgency/i })).toBeNull();
    expect(screen.getByLabelText('Upcoming POIs').style.overflowY).toBe(
      'hidden'
    );
  });

  it('declares a height transition for changing table size', () => {
    render(
      <UpcomingPoisPanel
        state="available"
        pois={[poi(1), poi(2)]}
        currentTime={now}
      />
    );

    expect(screen.getByTestId('upcoming-pois-body').className).toContain(
      'upcoming-pois__body'
    );
  });

  it('uses numeric body heights for table rows and explicit states', () => {
    const { rerender } = render(
      <UpcomingPoisPanel
        state="available"
        pois={[poi(1), poi(2)]}
        currentTime={now}
      />
    );

    expect(screen.getByTestId('upcoming-pois-body').style.height).toBe(
      '6.5rem'
    );

    rerender(
      <UpcomingPoisPanel state="no_upcoming_pois" pois={[]} currentTime={now} />
    );

    expect(screen.getByTestId('upcoming-pois-body').style.height).toBe(
      '2.5rem'
    );
  });

  it.each([
    ['no_active_route', 'No active route.'],
    ['no_generated_pois', 'No generated POIs.'],
    ['no_upcoming_pois', 'No upcoming POIs.'],
    ['unavailable', 'Upcoming POIs unavailable.'],
  ] as const)('renders the %s state explicitly', (state, message) => {
    render(<UpcomingPoisPanel state={state} pois={[]} currentTime={now} />);

    expect(screen.getByText(message)).not.toBeNull();
  });
});
