/** @vitest-environment jsdom */
import { render, screen, cleanup } from '@testing-library/react';
import { it, expect, vi, afterEach } from 'vitest';
import '@testing-library/jest-dom/vitest';
vi.mock('../../components/common/RouteMap', () => ({
  RouteMap: ({ anchoredARSpans }: { anchoredARSpans?: unknown }) => (
    <pre>{JSON.stringify(anchoredARSpans)}</pre>
  ),
}));
import { LegMapVisualization } from './LegMapVisualization';
afterEach(cleanup);
it('projects accepted occurrence spans for managed AR map overlays', () => {
  const anchor = {
    route_id: 'r',
    content_hash: 'h',
    segment_index: 0,
    fraction: 0,
    occurrence_id: 'a',
    source_time: '2026-10-25T12:00:00Z',
    latitude: 1,
    longitude: 2,
  };
  render(
    <LegMapVisualization
      routeCoordinates={[
        [1, 2],
        [2, 3],
        [3, 4],
      ]}
      satelliteConfig={{
        xband_transitions: [],
        ka_outages: [],
        ku_outages: [],
      }}
      aarConfig={{ segments: [], manualTracks: [] }}
      kaTransitions={[]}
      waypointNames={[]}
      availableWaypoints={[]}
      planningLeg={{
        id: 'l',
        ordinal: 1,
        departure_airport: 'A',
        arrival_airport: 'B',
        departure_time: anchor.source_time,
        arrival_time: '2026-10-25T13:00:00Z',
        route: {
          route_id: 'r',
          source_id: 's',
          content_hash: 'h',
          filename: 'r.kml',
        },
      }}
      planningDraft={{
        ar_corrections: [
          {
            id: 'ar',
            track: 'Track',
            entry_time: anchor.source_time,
            exit_time: '2026-10-25T13:00:00Z',
            source_time_precision: 'second',
            start_anchor: anchor,
            end_anchor: {
              ...anchor,
              segment_index: 2,
              occurrence_id: 'c',
              latitude: 3,
              longitude: 4,
            },
            match_status: 'matched',
          },
        ],
      }}
    />
  );
  expect(
    screen.getByText(/"coordinates":\[\[1,2\],\[2,3\],\[3,4\]\]/)
  ).toBeInTheDocument();
});
