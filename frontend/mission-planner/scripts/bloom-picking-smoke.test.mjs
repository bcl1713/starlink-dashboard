import { test } from 'node:test';
import assert from 'node:assert/strict';
import { PerspectiveCamera, Vector3 } from 'three';
import { verifyPoiPicking } from './bloom-picking-smoke.mjs';

// Model a broken browser where only exact center clicks dispatch R3F picks.
// The acceptance helper must reject it rather than read the previous status.
test('pointer smoke rejects an offset click that dispatches no new pick', async () => {
  const width = 1920,
    height = 810;
  const camera = new PerspectiveCamera(45, width / height, 0.1, 100);
  camera.position.set(0, 2, 6.8);
  camera.lookAt(0, 0, 0);
  camera.updateMatrixWorld();
  const targets = [
    [16, -65, 'charlie'],
    [35, -90, 'alpha'],
    [42, -30, 'bravo'],
  ].map(([lat, lon, id]) => {
    const rlat = (lat * Math.PI) / 180,
      rlon = (lon * Math.PI) / 180;
    const p = new Vector3(
      2.000001 * Math.cos(rlat) * Math.cos(rlon),
      2.000001 * Math.sin(rlat),
      -2.000001 * Math.cos(rlat) * Math.sin(rlon)
    ).project(camera);
    return { id, x: ((p.x + 1) * width) / 2, y: ((1 - p.y) * height) / 2 };
  });
  let status = 'Ready';
  const locator = {
    textContent: async () => status,
    filter: ({ hasText }) => ({
      waitFor: async () => {
        if (
          hasText instanceof RegExp
            ? !hasText.test(status)
            : !status.includes(hasText)
        )
          throw new Error('Expected a new pick');
      },
    }),
  };
  const page = {
    getByLabel: () => ({ selectOption: async () => {} }),
    locator: (selector) =>
      selector === 'canvas'
        ? { boundingBox: async () => ({ x: 0, y: 0, width, height }) }
        : locator,
    mouse: {
      click: async (x, y) => {
        const hit = targets.find((t) => Math.hypot(t.x - x, t.y - y) < 1);
        if (hit) status = `Picked synthetic POI: ${hit.id}`;
      },
    },
  };
  await assert.rejects(
    verifyPoiPicking(
      page,
      async () => {},
      async () => ({ camera: [0, 2, 6.8] })
    ),
    /Expected a new pick/
  );
});
