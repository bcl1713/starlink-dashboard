import { expect, it } from 'vitest';
import * as THREE from 'three';
import {
  pickAviationFeatures,
  inspectionReports,
  resolveAviationSelection,
} from './aviation-inspection';
import { createAviationDrawing, earthPoint } from './aviation-renderer';
import { emptyAviationView, type AviationView } from './aviation-controller';
import { parseAviationFeatures } from '@/services/aviation-features';
import { NOW, station, advisory, collection } from './fixtures';
import type { AviationLayer } from '@/services/aviation-weather';
import { visibleSigmetReports } from './sigmet-picking';

const viewport = { width: 1000, height: 1000 };
it('limits the keyboard inspection list to SIGMETs visible on the map', () => {
  const view = viewFor([advisory()], 'sigmet');
  try {
    expect(visibleSigmetReports(view, cameraAt(0.5, 0.5), viewport)).toEqual([{layer:'sigmet',id:'test-advisory'}]);
    expect(visibleSigmetReports(view, cameraAt(0,180), viewport)).toEqual([]);
  } finally { dispose(view); }
});
it('picks the visible advisory interior at close zoom', () => {
  const report = advisory();
  report.geometry.coordinates = [
    [
      [-80, 34],
      [-67, 34],
      [-67, 46],
      [-80, 46],
      [-80, 34],
    ],
    [
      [-76, 38],
      [-72, 38],
      [-72, 42],
      [-76, 42],
      [-76, 38],
    ],
  ];
  const view = viewFor([report], 'sigmet');
  const camera = cameraAt(36, -78);
  camera.position.normalize().multiplyScalar(3);
  camera.updateMatrixWorld();
  try {
    expect(
      pickAviationFeatures(view, camera, { x: 500, y: 500 }, viewport)
    ).toEqual([{ layer: 'sigmet', id: 'test-advisory' }]);
  } finally {
    dispose(view);
  }
});
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
it('exposes overlapping bulletins while excluding holes and the far side', () => {
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
it('picks both halves of an antimeridian advisory', () => {
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
      ).toEqual([{layer: 'sigmet', id: 'test-advisory'}]);
  } finally {
    dispose(view);
  }
});

it('resolves admitted SIGMET report selection', () => {
  const view = viewFor([advisory()], 'sigmet');
  try {
    expect(inspectionReports(view).map(r => r.selection)).toEqual([{layer: 'sigmet', id: 'test-advisory'}]);
    expect(
      resolveAviationSelection(view, { layer: 'sigmet', id: 'test-advisory' })?.id
    ).toBe('test-advisory');
  } finally {
    dispose(view);
  }
});
