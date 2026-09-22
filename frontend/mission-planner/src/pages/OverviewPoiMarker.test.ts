/** @vitest-environment jsdom */

import { cleanup, render, screen } from '@testing-library/react';
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import * as THREE from 'three';
import type { OverviewUpcomingPoi } from '@/services/overview-upcoming-pois';

const renderedStarMarker = vi.fn();

vi.mock('./OverviewStarMarker', async () => {
  const React = await import('react');
  return {
    StarMarker: (props: unknown) => {
      renderedStarMarker(props);
      return React.createElement('div', { 'data-testid': 'star-marker' });
    },
  };
});

vi.mock('@react-three/drei', async () => {
  const React = await import('react');
  return {
    Html: ({ children }: { children: React.ReactNode }) =>
      React.createElement('div', { 'data-testid': 'html-label' }, children),
  };
});

import { OverviewPoiMarker } from './OverviewPoiMarker';

afterEach(() => {
  cleanup();
  renderedStarMarker.mockReset();
});

const departurePoi: OverviewUpcomingPoi = {
  poi_id: 'departure-kadw',
  name: 'KADW',
  kind: 'departure',
  latitude: 38.85,
  longitude: -76.93,
  expected_arrival_time: '2026-09-22T12:00:00.000Z',
  eta_seconds: null,
  estimated_arrival_time: null,
  eta_type: null,
  upcoming: false,
  map_retained: true,
};

describe('OverviewPoiMarker', () => {
  it('renders one imported endpoint label through the shared star marker', () => {
    render(
      React.createElement(OverviewPoiMarker, {
        poi: departurePoi,
        color: '#22c55e',
        globeOccluder: { current: new THREE.Group() },
      })
    );

    expect(renderedStarMarker).toHaveBeenCalledWith(
      expect.objectContaining({
        coordinate: { latitude: 38.85, longitude: -76.93 },
        color: '#22c55e',
        size: 0.1,
      })
    );
    expect(screen.getByText('KADW')).not.toBeNull();
  });
});
