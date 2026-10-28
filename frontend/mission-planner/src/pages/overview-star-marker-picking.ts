import * as THREE from 'three';
import { isStarMarkerVisible } from './overview-star-marker-rendering';

export const ignoreStarMarkerRaycast = () => {};

/** A screen-space disk for the experiment's POIs; owns no drawable resources. */
export function starMarkerPickRaycast(
  radiusPixels: number,
  viewportHeight: number
) {
  const center = new THREE.Vector3();
  const view = new THREE.Vector3();
  const normal = new THREE.Vector3();
  const plane = new THREE.Plane();
  const point = new THREE.Vector3();
  return function (
    this: THREE.Object3D,
    raycaster: THREE.Raycaster,
    hits: THREE.Intersection[]
  ) {
    const camera = raycaster.camera;
    if (
      !(camera instanceof THREE.PerspectiveCamera) ||
      !(radiusPixels > 0) ||
      !(viewportHeight > 0)
    )
      return;
    this.getWorldPosition(center);
    // Raycaster itself does not apply Earth occlusion or Object3D.visible.
    if (!isStarMarkerVisible(center, camera)) return;
    const depth = -view.copy(center).applyMatrix4(camera.matrixWorldInverse).z;
    if (depth <= 0) return;
    const worldRadius =
      (radiusPixels *
        2 *
        depth *
        Math.tan(THREE.MathUtils.degToRad(camera.getEffectiveFOV()) / 2)) /
      viewportHeight;
    camera.getWorldDirection(normal);
    plane.setFromNormalAndCoplanarPoint(normal, center);
    if (
      !raycaster.ray.intersectPlane(plane, point) ||
      point.distanceToSquared(center) > worldRadius * worldRadius
    )
      return;
    const distance = raycaster.ray.origin.distanceTo(point);
    if (distance < raycaster.near || distance > raycaster.far) return;
    hits.push({ distance, point: point.clone(), object: this });
  };
}
