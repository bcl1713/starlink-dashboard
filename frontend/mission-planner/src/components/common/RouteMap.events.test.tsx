/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { Browser } from 'leaflet';
import { afterEach, beforeEach, expect, it } from 'vitest';
import { RouteMap } from './RouteMap';

const originalSvg = Browser.svg;
beforeEach(() =>
  Object.defineProperty(Browser, 'svg', { value: true, configurable: true })
);
afterEach(() => {
  cleanup();
  Object.defineProperty(Browser, 'svg', {
    value: originalSvg,
    configurable: true,
  });
});

it('shows AR boundaries and independently hides each event group on the real route map', () => {
  const { container } = render(
    <RouteMap
      coordinates={[
        [0, 170],
        [0, -170],
      ]}
      anchoredARSpans={[
        {
          id: 'ar',
          label: 'Refuel',
          coordinates: [
            [0, 175],
            [0, -175],
          ],
        },
      ]}
      xbandTransitions={[
        { id: 'x', latitude: 0, longitude: 178, target_satellite_id: 'X-2' },
      ]}
      kaTransitions={[
        {
          latitude: 0,
          longitude: 179,
          fromSatellite: 'POR',
          toSatellite: 'AOR',
          timestamp: '2026-10-14T12:30:00Z',
        },
      ]}
      kuOutages={[
        { id: 'ku', start_time: '2026-10-14T12:15:00Z', duration_seconds: 600 },
      ]}
      timelinePreview={{
        mission_leg_id: 'leg',
        created_at: '2026-10-14T12:00:00Z',
        segments: [],
        samples: [
          { timestamp: '2026-10-14T12:00:00Z', latitude: 0, longitude: 170 },
          { timestamp: '2026-10-14T13:00:00Z', latitude: 0, longitude: -170 },
        ],
      }}
    />
  );
  const marker = (name: string) =>
    container.querySelector(`.leaflet-marker-icon[title="${name}"]`);
  expect(marker('AR Start')).not.toBeNull();
  expect(marker('AR End')).not.toBeNull();
  expect(marker('Starshield Loss')).not.toBeNull();
  for (const [layer, title] of [
    ['Flight events', 'AR Start'],
    ['X-band events', 'X-Band Transition'],
    ['Ka-band events', 'Ka Transition'],
    ['Starshield events', 'Starshield Loss'],
  ]) {
    const control = screen.getByRole('checkbox', { name: layer });
    fireEvent.click(control);
    expect(marker(title)).toBeNull();
    fireEvent.click(control);
    expect(marker(title)).not.toBeNull();
  }
});

it('renders named-waypoint and manual-track AR endpoints', () => {
  const { container } = render(
    <RouteMap
      coordinates={[
        [0, 0],
        [0, 10],
      ]}
      waypointObjects={[
        { name: 'start', latitude: 0, longitude: 2 },
        { name: 'end', latitude: 0, longitude: 4 },
      ]}
      aarSegments={[
        {
          id: 'window',
          start_waypoint_name: 'start',
          end_waypoint_name: 'end',
        },
      ]}
      manualAARTracks={[
        {
          id: 'track',
          name: 'Manual refuel',
          points: [
            { latitude: 0, longitude: 5 },
            { latitude: 0, longitude: 6 },
          ],
        },
      ]}
    />
  );
  expect(
    container.querySelectorAll('.leaflet-marker-icon[title="AR Start"]')
  ).toHaveLength(2);
  expect(
    container.querySelectorAll('.leaflet-marker-icon[title="AR End"]')
  ).toHaveLength(2);
});

it.each([false, true])(
  'inactive_pois_hidden_in_all_route_maps saved=%s',
  (saved) => {
    const { container } = render(
      <RouteMap
        coordinates={[
          [0, 0],
          [0, 10],
        ]}
        transportAvailability={{ X: false, Ka: false, Ku: false }}
        xbandTransitions={[
          { id: 'x', latitude: 0, longitude: 4, target_satellite_id: 'X-2' },
        ]}
        kaTransitions={[
          {
            latitude: 0,
            longitude: 5,
            fromSatellite: 'POR',
            toSatellite: 'AOR',
            timestamp: '2026-10-25T12:00:00Z',
          },
        ]}
        timelinePreview={
          saved
            ? {
                mission_leg_id: 'l',
                created_at: 'now',
                segments: [],
                map_pois: [
                  {
                    name: 'Inactive X',
                    kind: 'x_band_transition',
                    latitude: 0,
                    longitude: 4,
                    transport_active: false,
                  },
                  {
                    name: 'Arrival',
                    kind: 'arrival',
                    latitude: 0,
                    longitude: 10,
                  },
                ],
              }
            : null
        }
      />
    );
    expect(container.querySelectorAll('.leaflet-marker-icon')).toHaveLength(
      saved ? 1 : 2
    );
    expect(
      container.querySelector('.leaflet-marker-icon[title="X-Band Transition"]')
    ).toBeNull();
    expect(
      container.querySelector('.leaflet-marker-icon[title="Ka Transition"]')
    ).toBeNull();
  }
);

it('retains_prepared_historical_eligible_pois_while_suppressing_inactive_future_cues', () => {
  const { container } = render(
    <RouteMap
      coordinates={[
        [0, 0],
        [0, 10],
      ]}
      transportAvailability={{ X: false }}
      timelinePreview={{
        mission_leg_id: 'l',
        created_at: 'now',
        segments: [],
        map_pois: [
          {
            name: 'Past X',
            kind: 'x_band_transition',
            latitude: 0,
            longitude: 1,
            transport_active: true,
          },
          {
            name: 'Future X',
            kind: 'x_band_transition',
            latitude: 0,
            longitude: 8,
            transport_active: false,
          },
        ],
      }}
    />
  );
  expect(
    container.querySelector('.leaflet-marker-icon[title="Past X"]')
  ).not.toBeNull();
  expect(
    container.querySelector('.leaflet-marker-icon[title="Future X"]')
  ).toBeNull();
});
