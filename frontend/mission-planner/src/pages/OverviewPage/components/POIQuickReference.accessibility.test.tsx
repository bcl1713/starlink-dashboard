import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const formatterMock = vi.hoisted(() => ({ select: vi.fn() }));

vi.mock('../formatters', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../formatters')>();
  return {
    ...actual,
    selectApplicablePOIs: formatterMock.select.mockImplementation(
      actual.selectApplicablePOIs
    ),
  };
});

import { POIQuickReference } from './POIQuickReference';
import { poi, slot } from './metric-panel-test-fixtures';

describe('POIQuickReference accessibility and selection', () => {
  it('selects once per POI array identity and keeps one named table tree', () => {
    const pois = [
      poi({ poi_id: 'a', name: 'A', eta_seconds: 60 }),
      poi({ poi_id: 'b', name: 'B', eta_seconds: 60 }),
      poi({
        poi_id: 'excluded',
        name: 'Excluded',
        eta_seconds: 1,
        route_aware_status: 'already_passed',
      }),
    ];
    const response = {
      total: pois.length,
      timestamp: '2026-08-29T12:00:00Z',
      pois,
    };
    const { rerender } = render(
      <POIQuickReference slot={slot(response)} retryPending={false} />
    );

    expect(formatterMock.select).toHaveBeenCalledTimes(1);
    rerender(<POIQuickReference slot={slot(response)} retryPending={false} />);
    expect(formatterMock.select).toHaveBeenCalledTimes(1);

    rerender(
      <POIQuickReference
        slot={slot({ ...response, pois: [...pois] })}
        retryPending={false}
      />
    );
    expect(formatterMock.select).toHaveBeenCalledTimes(2);
    expect(screen.getAllByRole('table')).toHaveLength(1);
    expect(
      screen.getByRole('table', { name: 'POI Quick Reference (Top 5)' })
    ).toBeVisible();
    expect(screen.getAllByRole('row')[1]).toHaveTextContent('A');
    expect(screen.getAllByRole('row')[2]).toHaveTextContent('B');
    expect(screen.queryByText('Excluded')).not.toBeInTheDocument();
  });
});
