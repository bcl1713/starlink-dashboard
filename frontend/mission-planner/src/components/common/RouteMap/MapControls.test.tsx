/** @vitest-environment jsdom */
import { cleanup, render } from '@testing-library/react';
import { Browser, Map, latLngBounds } from 'leaflet';
import { afterEach, expect, it, vi } from 'vitest';

const state = vi.hoisted(() => ({ map: null as Map | null }));
vi.mock('react-leaflet', () => ({ useMap: () => state.map }));
import { MapControls } from './MapControls';

const original3d = Browser.any3d;
afterEach(() => {
  cleanup();
  state.map?.remove();
  state.map = null;
  Object.defineProperty(Browser, 'any3d', {
    value: original3d,
    configurable: true,
  });
  document.body.replaceChildren();
});

it('fits the real route and can unmount before a zoom transition completes', async () => {
  // Exercise the same accelerated Leaflet transition path as Chromium.
  Object.defineProperty(Browser, 'any3d', { value: true, configurable: true });
  const container = document.createElement('div');
  Object.defineProperties(container, {
    clientWidth: { value: 800 },
    clientHeight: { value: 600 },
  });
  document.body.append(container);
  const map = new Map(container, {
    center: [0, 0],
    zoom: 6,
    zoomControl: false,
    attributionControl: false,
  });
  state.map = map;
  const bounds = latLngBounds([-1, -1], [1, 1]);
  const mapRef = { current: null as Map | null };
  const view = render(
    <MapControls bounds={bounds} mapRef={mapRef} coordinateCount={2} />
  );
  await new Promise((resolve) => setTimeout(resolve, 40));
  expect(mapRef.current).toBe(map);
  expect(map.getBounds().contains(bounds)).toBe(true);
  view.unmount();
  map.remove();
  state.map = null;
  await new Promise((resolve) => setTimeout(resolve, 300));
  // Vitest must observe any uncaught delayed Leaflet callback as a failure.
});
