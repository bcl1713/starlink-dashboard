/** @vitest-environment jsdom */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { OverviewPlannedSatelliteCard } from './OverviewPlannedSatelliteCard';
import type { PlannedSatelliteState } from './overview-planned-satellite';
afterEach(cleanup);
describe('planning card', () => {
  it.each<[PlannedSatelliteState, string]>([
    [{ kind: 'selected', satelliteId: 'X-6' }, 'X-6'],
    [{ kind: 'none' }, 'NO SATELLITE SELECTED'],
    [{ kind: 'loading' }, 'LOADING…'],
    [{ kind: 'unavailable' }, 'UNAVAILABLE'],
  ])('presents %j as planning data', (state, value) => {
    render(<OverviewPlannedSatelliteCard state={state} />);
    const card = screen.getByRole('region', { name: 'Planned satellite' });
    expect(Array.from(card.children, (row) => row.textContent)).toEqual([
      'X-BAND',
      value,
      'PLANNED SATELLITE',
    ]);
    expect(card.querySelector('img, svg, time, [role="status"]')).toBeNull();
  });
});
