import { expect, it } from 'vitest';
import * as THREE from 'three';
import { pickAviationFeatures } from './aviation-inspection';
import { createAviationDrawing, earthPoint } from './aviation-renderer';
import { emptyAviationView, type AviationView } from './aviation-controller';
import { parseAviationFeatures } from '@/services/aviation-features';
import { NOW, station, advisory, collection } from './fixtures';
import type { AviationLayer } from '@/services/aviation-weather';

const viewport = { width: 1000, height: 1000 };
it('includes the visible glyph footprint when close zoom makes it larger than the minimum tap target', () => {
  const taf = viewFor([station(true)], 'taf');
  const metar = viewFor([station()], 'metar');
  const camera = cameraAt();
  camera.position.x = 3;
  camera.aspect = 3840 / 2160;
  camera.updateProjectionMatrix();
  camera.updateMatrixWorld();
  try {
    // The north vertex of this diamond is 21.4 CSS pixels above its center.
    expect(
      pickAviationFeatures(
        taf,
        camera,
        { x: 1920, y: 1059 },
        { width: 3840, height: 2160 }
      )
    ).toEqual([{ layer: 'taf', id: 'test-station' }]);
    expect(
      pickAviationFeatures(
        taf,
        camera,
        { x: 1950, y: 1059 },
        { width: 3840, height: 2160 }
      )
    ).toEqual([]);
    camera.aspect = 1;
    camera.updateProjectionMatrix();
    expect(
      pickAviationFeatures(
        metar,
        camera,
        { x: 3016, y: 3000 },
        { width: 6000, height: 6000 }
      )
    ).toEqual([{ layer: 'metar', id: 'test-station' }]);
    expect(
      pickAviationFeatures(
        metar,
        camera,
        { x: 3019, y: 3019 },
        { width: 6000, height: 6000 }
      )
    ).toEqual([{ layer: 'metar', id: 'test-station' }]);
  } finally {
    dispose(taf);
    dispose(metar);
  }
});
function cameraAt(lat = 0, lon = 0) {
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
  camera.position.copy(earthPoint(lat, lon).normalize().multiplyScalar(5));
  camera.lookAt(0, 0, 0);
  camera.updateMatrixWorld();
  return camera;
}
function viewFor(features: unknown[], layer: AviationLayer): AviationView {
  const data = parseAviationFeatures(collection(features), layer);
  return {
    ...emptyAviationView,
    now: NOW,
    layers: {
      ...emptyAviationView.layers,
      [layer]: {
        state: 'current',
        data,
        drawing: createAviationDrawing(data, layer, NOW),
      },
    },
  };
}
function dispose(view: AviationView) {
  for (const item of Object.values(view.layers)) item.drawing?.dispose();
}
it('picks co-located station products in CSS pixels while excluding far-side stations', () => {
  const front = station();
  const back = station();
  back.id = 'back';
  back.properties.station_id = 'BACK';
  back.geometry.coordinates = [180, 0];
  const view = viewFor([front, back], 'metar');
  const taf = viewFor([station(true)], 'taf');
  view.layers.taf = taf.layers.taf;
  try {
    expect(
      pickAviationFeatures(view, cameraAt(), { x: 505, y: 500 }, viewport)
    ).toEqual([
      { layer: 'metar', id: 'test-station' },
      { layer: 'taf', id: 'test-station' },
    ]);
    expect(
      pickAviationFeatures(view, cameraAt(), { x: 550, y: 500 }, viewport)
    ).toEqual([]);
    view.layers.metar.state = 'off';
    expect(
      pickAviationFeatures(view, cameraAt(), { x: 500, y: 500 }, viewport)
    ).toEqual([{ layer: 'taf', id: 'test-station' }]);
    view.now = NOW + 3600000;
    expect(
      pickAviationFeatures(view, cameraAt(), { x: 500, y: 500 }, viewport)
    ).toEqual([]);
  } finally {
    dispose(view);
  }
});
it('picks each overlapping bulletin once, but never a polygon hole or the hidden hemisphere', () => {
  const first = advisory(),
    second = { ...advisory(), id: 'overlap' };
  const view = viewFor([first, second], 'sigmet');
  try {
    expect(
      pickAviationFeatures(
        view,
        cameraAt(0.5, 0.5),
        { x: 500, y: 500 },
        viewport
      )
        .map((f) => f.id)
        .sort()
    ).toEqual(['overlap', 'test-advisory']);
    expect(
      pickAviationFeatures(view, cameraAt(2, 2), { x: 500, y: 500 }, viewport)
    ).toEqual([]);
    expect(
      pickAviationFeatures(
        view,
        cameraAt(0.5, -179.5),
        { x: 500, y: 500 },
        viewport
      )
    ).toEqual([]);
  } finally {
    dispose(view);
  }
});
it('associates both halves of an antimeridian advisory with the same bulletin', () => {
  const a = {
    ...advisory(),
    geometry: {
      type: 'MultiPolygon',
      coordinates: [
        [
          [
            [170, 5],
            [180, 5],
            [180, 15],
            [170, 15],
            [170, 5],
          ],
        ],
        [
          [
            [-180, 5],
            [-170, 5],
            [-170, 15],
            [-180, 15],
            [-180, 5],
          ],
        ],
      ],
    },
  };
  const view = viewFor([a], 'sigmet');
  try {
    for (const lon of [179, -179])
      expect(
        pickAviationFeatures(
          view,
          cameraAt(10, lon),
          { x: 500, y: 500 },
          viewport
        )
      ).toEqual([{ layer: 'sigmet', id: 'test-advisory' }]);
  } finally {
    dispose(view);
  }
});
