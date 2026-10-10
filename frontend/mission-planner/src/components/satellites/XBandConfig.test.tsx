/** @vitest-environment jsdom */
import { render, screen, cleanup } from '@testing-library/react';
import { it, expect, vi, afterEach } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { XBandConfig } from './XBandConfig';
afterEach(cleanup);
it('shows accepted exact UTC provenance for an anchored transition', () => {
  render(
    <XBandConfig
      startingSatellite="WEST"
      availableSatellites={['WEST']}
      onStartingSatelliteChange={vi.fn()}
      onTransitionsChange={vi.fn()}
      transitions={[
        {
          id: 's',
          latitude: 1,
          longitude: 2,
          target_satellite_id: 'WEST',
          anchor: {
            route_id: 'r',
            content_hash: 'h',
            segment_index: 0,
            fraction: 0,
            occurrence_id: 'occ',
            source_time: '2026-10-25T12:04:17Z',
            latitude: 1,
            longitude: 2,
          },
        },
      ]}
    />
  );
  expect(screen.getByText(/UTC 2026-10-25T12:04:17Z/)).toBeInTheDocument();
});
