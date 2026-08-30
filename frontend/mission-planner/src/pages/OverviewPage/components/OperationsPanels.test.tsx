import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { GroundEntryPointPanel } from './GroundEntryPointPanel';
import { ObstructionGauge } from './ObstructionGauge';
import { POIQuickReference } from './POIQuickReference';
import { poi, slot } from './metric-panel-test-fixtures';
import type {
  GroundEntryPoint,
  OverviewStatus,
} from '../../../types/monitoring';

describe('operations panels', () => {
  it('renders obstruction threshold and clamps meter display range', () => {
    render(
      <ObstructionGauge
        slot={slot({
          obstruction: { obstruction_percent: 25 },
        } as OverviewStatus)}
        retryPending={false}
        headingAs="h3"
      />
    );

    const meter = screen.getByRole('meter', {
      name: 'Obstruction percentage',
    });
    expect(meter).toHaveAttribute('aria-valuenow', '20');
    expect(meter).toHaveAttribute(
      'aria-valuetext',
      '25% - Critical, above 20% display range'
    );
    expect(screen.getByText(/above display range/)).toBeVisible();
  });

  it('renders only approved GEP fields and calls focus for valid coordinates', () => {
    const focus = vi.fn();
    const gep: GroundEntryPoint = {
      available: true,
      observed_at: '2026-08-29T12:00:00Z',
      generated_at: '2026-08-29T12:00:01Z',
      display: 'Seattle POP',
      city: 'Seattle',
      region: 'WA',
      country: 'US',
      latitude: 47.6,
      longitude: -122.3,
    };

    render(
      <GroundEntryPointPanel
        slot={slot(gep)}
        retryPending={false}
        onFocusCoordinates={focus}
      />
    );

    expect(screen.getByText('Seattle POP')).toBeVisible();
    expect(screen.queryByText('generated_at')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Focus map' }));
    expect(focus).toHaveBeenCalledWith({ latitude: 47.6, longitude: -122.3 });
  });

  it('renders POI top five with Task7 exclusions and urgency boundaries', () => {
    render(
      <POIQuickReference
        retryPending={false}
        slot={slot({
          total: 7,
          timestamp: '2026-08-29T12:00:00Z',
          pois: [
            poi({
              poi_id: 'behind',
              name: 'Behind',
              eta_seconds: 1,
              course_status: 'behind',
            }),
            poi({ poi_id: 'a', name: 'A', eta_seconds: 899 }),
            poi({ poi_id: 'b', name: 'B', eta_seconds: 900 }),
            poi({ poi_id: 'c', name: 'C', eta_seconds: 1800 }),
            poi({ poi_id: 'd', name: 'D', eta_seconds: 3600 }),
            poi({ poi_id: 'e', name: 'E', eta_seconds: -1 }),
            poi({ poi_id: 'f', name: 'F', eta_seconds: 10_000 }),
          ],
        })}
      />
    );

    expect(screen.queryByText('Behind')).not.toBeInTheDocument();
    expect(screen.getByText('Most urgent')).toBeVisible();
    expect(screen.getByText('High')).toBeVisible();
    expect(screen.getByText('Moderate')).toBeVisible();
    expect(screen.getAllByText('Normal').length).toBeGreaterThan(0);
    expect(screen.getAllByRole('row')).toHaveLength(6);
  });
});
