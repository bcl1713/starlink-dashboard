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

  it.each([
    [4, 'Normal', '4% - Normal'],
    [5, 'Warning', '5% - Warning'],
    [10, 'Critical', '10% - Critical'],
    [-1, 'Unavailable', 'Unavailable'],
    [Number.NaN, 'Unavailable', 'Unavailable'],
    [Number.POSITIVE_INFINITY, 'Unavailable', 'Unavailable'],
    [101, 'Unavailable', 'Unavailable'],
  ])('renders exact obstruction threshold %s', (value, label, ariaText) => {
    render(
      <ObstructionGauge
        slot={slot({
          obstruction: { obstruction_percent: value },
        } as OverviewStatus)}
        retryPending={false}
      />
    );

    const meter = screen.getByRole('meter', {
      name: 'Obstruction percentage',
    });
    expect(
      screen.getByRole('region', { name: 'Obstruction %' })
    ).toHaveTextContent(label);
    expect(meter).toHaveAttribute('aria-valuetext', ariaText);
    if (Number.isFinite(value) && value >= 0 && value <= 100)
      expect(meter).toHaveAttribute('aria-valuenow');
    else expect(meter).not.toHaveAttribute('aria-valuenow');
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

  it('projects GEP available false as semantic unavailable without mutating source slot', () => {
    const gep: GroundEntryPoint = Object.freeze({
      available: false,
      observed_at: '2026-08-29T12:00:00Z',
      generated_at: '2026-08-29T12:00:01Z',
      display: 'Hidden POP',
      city: 'Seattle',
      region: 'WA',
      country: 'US',
      latitude: 47.6,
      longitude: -122.3,
    });
    const source = Object.freeze(slot(gep));

    render(<GroundEntryPointPanel slot={source} retryPending={false} />);

    const region = screen.getByRole('region', { name: 'Ground Entry Point' });
    expect(region).toHaveTextContent('Unavailable');
    expect(region).toHaveTextContent('Source 2026-08-29 12:30:00 UTC');
    expect(region).not.toHaveTextContent('Ready');
    expect(source.availability).toBe('available');
    expect(source.phase).toBe('ready');
    expect(source.data).toBe(gep);
  });

  it('renders POI top five with applicability exclusions and urgency boundaries', () => {
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
    expect(
      screen.getByRole('table', { name: 'POI Quick Reference (Top 5)' })
    ).toBeVisible();
  });

  it.each([
    [-1, 'Unavailable'],
    [Number.POSITIVE_INFINITY, 'Unavailable'],
  ])(
    'renders POI invalid ETA %s as unavailable in the visible top five',
    (eta, label) => {
      render(
        <POIQuickReference
          retryPending={false}
          slot={slot({
            total: 1,
            timestamp: '2026-08-29T12:00:00Z',
            pois: [
              poi({ poi_id: 'invalid', name: 'Invalid ETA', eta_seconds: eta }),
            ],
          })}
        />
      );

      const row = screen.getByRole('row', { name: /Invalid ETA/ });
      expect(row).toHaveTextContent(label);
      expect(row).toHaveTextContent('—');
    }
  );

  it('omits GEP focus button for invalid coordinates', () => {
    render(
      <GroundEntryPointPanel
        slot={slot({
          available: true,
          display: 'Bad POP',
          city: null,
          region: null,
          country: null,
          latitude: Infinity,
          longitude: -122.3,
          observed_at: null,
          generated_at: '2026-08-29T12:00:00Z',
        } as GroundEntryPoint)}
        retryPending={false}
        onFocusCoordinates={vi.fn()}
      />
    );

    expect(
      screen.queryByRole('button', { name: 'Focus map' })
    ).not.toBeInTheDocument();
    expect(screen.getByText('Coordinates')).toBeVisible();
  });
});
