/** @vitest-environment jsdom */
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import type { Timeline } from '../../services/timeline';
import { TimelinePreviewSection } from './TimelinePreviewSection';

afterEach(cleanup);
const timeline: Timeline = {
  mission_leg_id: 'synthetic-271',
  created_at: '2035-03-01T23:00:00Z',
  segments: [
    {
      id: 'one',
      start_time: '2035-03-01T23:00:00Z',
      end_time: '2035-03-02T01:05:30Z',
      status: 'nominal',
      x_state: 'available',
      ka_state: 'available',
      ku_state: 'offline',
      metadata: {
        notes: ['First note', 'Second note', 'Hidden diagnostic'],
        source_reasons: ['Detailed source reason'],
      },
    },
  ],
  coverage_events: [
    {
      timestamp: '2035-03-01T23:00:00Z',
      event_type: 'starting',
      coverage: ['POR'],
      reason: 'Starting Ka coverage: POR',
    },
    {
      timestamp: '2035-03-01T23:30:00Z',
      event_type: 'entry',
      satellite_id: 'IOR',
      coverage: ['IOR', 'POR'],
      reason: 'IOR footprint entry',
    },
    {
      timestamp: '2035-03-02T00:00:00Z',
      event_type: 'handoff',
      coverage: ['IOR', 'POR'],
      reason: 'Recommended handoff POR → IOR',
    },
    {
      timestamp: '2035-03-02T00:30:00Z',
      event_type: 'exit',
      satellite_id: 'POR',
      coverage: ['IOR'],
      reason: 'POR footprint exit',
    },
  ],
};

it('renders UTC dates across midnight, elapsed time, readable duration and each system state', () => {
  render(<TimelinePreviewSection timeline={timeline} isCalculating={false} />);
  expect(screen.getAllByText(/2035-03-01 23:00:00/).length).toBeGreaterThan(0);
  expect(screen.getByText(/2035-03-02 01:05:30/)).not.toBeNull();
  expect(screen.getByText('2h 5m 30s')).not.toBeNull();
  expect(screen.getByText('Ku: OFFLINE')).not.toBeNull();
  expect(screen.getByText('X: AVAILABLE')).not.toBeNull();
  expect(screen.getByText('Ka: AVAILABLE')).not.toBeNull();
  expect(screen.getAllByText('T+1h').length).toBeGreaterThan(0);
});

it('keeps footprint entry, recommended handoff and exit distinct with coverage still available', () => {
  render(<TimelinePreviewSection timeline={timeline} isCalculating={false} />);
  const table = screen.getByRole('table', { name: 'Ka coverage sequence' });
  const rows = within(table).getAllByRole('row');
  expect(rows).toHaveLength(5);
  expect(rows[2].textContent).toContain('IOR footprint entry');
  expect(rows[2].textContent).toContain('IOR, POR');
  expect(rows[3].textContent).toContain('Recommended handoff POR → IOR');
  expect(rows[4].textContent).toContain('POR footprint exit');
  expect(rows[4].textContent).toContain('IOR');
  expect(table.textContent).not.toContain('coverage lost');
});

it('makes every detailed source reason accessible', () => {
  render(<TimelinePreviewSection timeline={timeline} isCalculating={false} />);
  fireEvent.click(screen.getByText(/Details/));
  expect(screen.getByText('Hidden diagnostic')).not.toBeNull();
  expect(screen.getByText('Detailed source reason')).not.toBeNull();
});
