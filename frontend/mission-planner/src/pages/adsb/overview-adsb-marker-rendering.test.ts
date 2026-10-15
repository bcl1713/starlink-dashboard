import { expect, it } from 'vitest';
import * as THREE from 'three';
import {
  buildAdsbMarkerInstances,
  isAdsbMarkerVisible,
  adsbClickAllowed,
  createAdsbEarthOccluder,
} from './overview-adsb-marker-rendering';
import { projectAdsbContacts } from './overview-adsb-state';
import { ADSB_NOW, adsbContact, adsbSettings } from '@/test/adsb-fixtures';
import { ROUTE_OVERLAY_RADIUS } from '../globe-render-radii';

it('uses the actual globe transform for an analytic Earth intersection and respects ray distance bounds', () => {
  const globe = new THREE.Group();
  globe.position.set(3, 0, 0);
  globe.scale.setScalar(2);
  globe.updateMatrixWorld();
  const earth = createAdsbEarthOccluder({ current: globe });
  const ray = new THREE.Raycaster(
    new THREE.Vector3(3, 0, 10),
    new THREE.Vector3(0, 0, -1)
  );
  const [hit] = ray.intersectObject(earth, true);
  expect(hit.distance).toBe(6);
  expect(hit.point.toArray()).toEqual([3, 0, 4]);
  ray.far = 5;
  expect(ray.intersectObject(earth, true)).toEqual([]);
  ray.far = 20;
  ray.ray.origin.x = 10;
  expect(ray.intersectObject(earth, true)).toEqual([]);
});
it.each([
  [0, [0, 1, 0]],
  [90, [0, 0, -1]],
  [180, [0, -1, 0]],
  [270, [0, 0, 1]],
  [null, [0, 1, 0]],
] as const)(
  'orients track %s in the local tangent plane, preserves legal clearance',
  (track, direction) => {
    const views = projectAdsbContacts(
      [
        adsbContact({
          latitude: 0,
          longitude: 0,
          track_degrees: track,
          altitude: null,
        }),
      ],
      adsbSettings(),
      ADSB_NOW
    );
    const instances = buildAdsbMarkerInstances(views);
    const matrix = new THREE.Matrix4().fromArray(instances.current.matrices);
    const forward = new THREE.Vector3(0, 1, 0).transformDirection(matrix);
    direction.forEach((want, i) =>
      expect(forward.getComponent(i)).toBeCloseTo(want, 5)
    );
    expect(
      new THREE.Vector3().setFromMatrixPosition(matrix).length()
    ).toBeGreaterThan(ROUTE_OVERLAY_RADIUS);
    expect(instances.current.hexes).toEqual(['00AB12']);
    expect(instances.stale.hexes).toEqual([]);
  }
);
it('deduplicates instances without truncation and separates stale geometry treatment', () => {
  const views = projectAdsbContacts(
    Array.from({ length: 2000 }, (_, i) =>
      adsbContact({
        hex: i.toString(16).toUpperCase().padStart(6, '0'),
        position_observed_at_ms: ADSB_NOW - (i % 2 ? 40000 : 0),
      })
    ),
    adsbSettings(),
    ADSB_NOW
  );
  const data = buildAdsbMarkerInstances(views);
  expect(data.current.hexes.length + data.stale.hexes.length).toBe(2000);
  expect(data.stale.hexes).toHaveLength(1000);
});
it('rejects rear-side and outside-frustum contacts from interaction eligibility', () => {
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
  camera.position.set(0, 0, 10);
  camera.lookAt(0, 0, 0);
  camera.updateMatrixWorld();
  expect(isAdsbMarkerVisible(new THREE.Vector3(0, 0, 2.003), camera)).toBe(
    true
  );
  expect(isAdsbMarkerVisible(new THREE.Vector3(0, 0, -2.003), camera)).toBe(
    false
  );
  expect(isAdsbMarkerVisible(new THREE.Vector3(100, 0, 2.003), camera)).toBe(
    false
  );
});
it('distinguishes clicks from camera drags including an out-and-back drag', () => {
  expect(
    adsbClickAllowed(
      { x: 10, y: 10, maxDistance: 0, cancelled: false },
      { x: 13, y: 14 }
    )
  ).toBe(true);
  expect(
    adsbClickAllowed(
      { x: 10, y: 10, maxDistance: 8, cancelled: false },
      { x: 10, y: 10 }
    )
  ).toBe(false);
  expect(
    adsbClickAllowed(
      { x: 10, y: 10, maxDistance: 0, cancelled: true },
      { x: 10, y: 10 }
    )
  ).toBe(false);
});
