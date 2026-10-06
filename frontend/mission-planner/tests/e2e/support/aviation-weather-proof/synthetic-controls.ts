import { active, advisoryMesh, type Feature } from './advisory-renderer';
import { barb } from './sampling';
import * as THREE from 'three';
import { earthPoint } from './grid-renderer';
export function geometryControls(reserve: (bytes: number) => () => void) {
  const feature: Feature = {
    id: 'synthetic-hole',
    geometry: {
      type: 'Polygon',
      coordinates: [
        [
          [-10, -10],
          [10, -10],
          [10, 10],
          [-10, 10],
          [-10, -10],
        ],
        [
          [-2, -2],
          [-2, 2],
          [2, 2],
          [2, -2],
          [-2, -2],
        ],
      ],
    },
    properties: {
      validity: { start_ms: 0, end_ms: 10 },
      cancellation: { cancelled: false },
      status: 'active',
    },
  };
  const release = reserve(4800000);
  const owned = new Set<{ dispose: () => void }>();
  try {
    const object = advisoryMesh([feature], 5);
    owned.add(object);
    object.mesh.updateMatrixWorld(true);
    const ray = (lat: number, lon: number) => {
      const p = earthPoint(lat, lon, 5);
      return new THREE.Raycaster(
        p,
        p.clone().normalize().negate()
      ).intersectObject(object.mesh).length;
    };
    const result = {
      holes: ray(0, 0) === 0 && ray(5, 5) > 0,
      expiry: !active(feature, 10),
      cancelled: !active(
        {
          ...feature,
          properties: {
            ...feature.properties,
            cancellation: { cancelled: true },
          },
        },
        5
      ),
      directional: barb(10, 0).fromEast === -1 && barb(10, 0).knots === 20,
      advisory_dateline: false,
    };
    object.dispose();
    owned.delete(object);
    const seamFeature: Feature = {
      ...feature,
      geometry: {
        type: 'MultiPolygon',
        coordinates: [
          [
            [
              [175, -5],
              [180, -5],
              [180, 5],
              [175, 5],
              [175, -5],
            ],
          ],
          [
            [
              [-180, -5],
              [-175, -5],
              [-175, 5],
              [-180, 5],
              [-180, -5],
            ],
          ],
        ],
      },
    };
    const seam = advisoryMesh([seamFeature], 5);
    owned.add(seam);
    seam.mesh.updateMatrixWorld(true);
    const hits = (lon: number) => {
      const p = earthPoint(0, lon, 5);
      return new THREE.Raycaster(
        p,
        p.clone().normalize().negate()
      ).intersectObject(seam.mesh).length;
    };
    result.advisory_dateline = hits(178) > 0 && hits(-178) > 0 && hits(0) === 0;
    return result;
  } finally {
    for (const object of owned) object.dispose();
    release();
  }
}
