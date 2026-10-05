import * as THREE from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import type { GlobeCoordinate } from './globe-route';
import { globePosition } from './globe-coordinates';
import { ROUTE_OVERLAY_RADIUS } from './globe-render-radii';

export const CORE_COLOR = '#ffffff';
export const DEFAULT_GLOW_SIZE_PIXELS = 34;

export type StarMarkerPositionProps =
  | {
      coordinate: GlobeCoordinate;
      position?: never;
    }
  | {
      coordinate?: never;
      position: [number, number, number];
    };

export function resolveStarMarkerPosition(
  props: StarMarkerPositionProps
): [number, number, number] {
  if (props.position) {
    return props.position;
  }

  return globePosition(
    props.coordinate.latitude,
    props.coordinate.longitude,
    ROUTE_OVERLAY_RADIUS
  );
}

export function projectedCoreRadius({
  configuredRadius,
  maxCorePixels,
  distance,
  cameraFovDegrees,
  viewportHeight,
}: {
  configuredRadius: number;
  maxCorePixels: number;
  distance: number;
  cameraFovDegrees: number;
  viewportHeight: number;
}) {
  if (
    !Number.isFinite(distance) ||
    !Number.isFinite(cameraFovDegrees) ||
    viewportHeight <= 0 ||
    distance <= 0 ||
    maxCorePixels <= 0
  ) {
    return configuredRadius;
  }

  const visibleHeight =
    2 * distance * Math.tan((cameraFovDegrees * Math.PI) / 360);
  const maxRadius = (maxCorePixels / 2) * (visibleHeight / viewportHeight);

  return Math.min(configuredRadius, maxRadius);
}

const haloVertexShader = `
  uniform float uSizePixels;
  uniform float uPixelRatio;
  uniform float uDepthBias;

  void main() {
    vec4 modelViewPosition = modelViewMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * modelViewPosition;
    gl_Position.z -= uDepthBias * gl_Position.w;
    gl_PointSize = uSizePixels * uPixelRatio;
  }
`;

const haloFragmentShader = `
  uniform vec3 uColor;
  uniform float uStrength;
  uniform float uFalloff;

  void main() {
    vec2 point = gl_PointCoord - vec2(0.5);
    float distanceFromCenter = length(point);
    if (distanceFromCenter > 0.5) discard;

    float alpha = 1.0 - smoothstep(0.0, 0.5, distanceFromCenter);
    alpha = pow(alpha, uFalloff);
    gl_FragColor = vec4(uColor * uStrength, alpha);
  }
`;

export type StarMarkerHaloLayer = {
  material: THREE.ShaderMaterial;
  renderOrder: number;
};

export type StarMarkerHaloResources = {
  geometry: THREE.BufferGeometry;
  layers: readonly StarMarkerHaloLayer[];
};

function createHaloMaterial({
  color,
  sizePixels,
  strength,
  falloff,
}: {
  color: string;
  sizePixels: number;
  strength: number;
  falloff: number;
}) {
  return new THREE.ShaderMaterial({
    uniforms: {
      uColor: { value: new THREE.Color(color) },
      uStrength: { value: strength },
      uFalloff: { value: falloff },
      uSizePixels: { value: sizePixels },
      uPixelRatio: { value: 1 },
      uDepthBias: { value: 0.00001 },
    },
    vertexShader: haloVertexShader,
    fragmentShader: haloFragmentShader,
    transparent: true,
    depthTest: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    toneMapped: false,
  });
}

export function createStarMarkerHaloResources({
  color,
  glowSizePixels,
  glowIntensity,
}: {
  color: string;
  glowSizePixels: number;
  glowIntensity: number;
}): StarMarkerHaloResources {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute(
    'position',
    new THREE.Float32BufferAttribute([0, 0, 0], 3)
  );

  const intensity = Math.max(0, glowIntensity);
  const layers: StarMarkerHaloLayer[] = [
    {
      material: createHaloMaterial({
        color,
        sizePixels: glowSizePixels,
        strength: 0.28 * intensity,
        falloff: 2.6,
      }),
      renderOrder: 1,
    },
    {
      material: createHaloMaterial({
        color,
        sizePixels: glowSizePixels * (18 / 34),
        strength: 0.62 * intensity,
        falloff: 2.2,
      }),
      renderOrder: 2,
    },
    {
      material: createHaloMaterial({
        color,
        sizePixels: glowSizePixels * (9 / 34),
        strength: 0.95 * intensity,
        falloff: 1.9,
      }),
      renderOrder: 3,
    },
    {
      material: createHaloMaterial({
        color: CORE_COLOR,
        sizePixels: 3,
        strength: 2.3 * intensity,
        falloff: 1.3,
      }),
      renderOrder: 4,
    },
  ];

  return { geometry, layers };
}

export function setStarMarkerHaloPixelRatio(
  resources: StarMarkerHaloResources,
  pixelRatio: number
) {
  for (const layer of resources.layers) {
    layer.material.uniforms.uPixelRatio.value = pixelRatio;
  }
}

export function disposeStarMarkerHaloResources({
  geometry,
  layers,
}: StarMarkerHaloResources) {
  geometry.dispose();
  for (const layer of layers) {
    layer.material.dispose();
  }
}

/** A normalized chevron shared by the own-aircraft and instanced ADS-B markers. */
export function createStarMarkerChevronResources({
  color,
  coreColor = color,
  glowIntensity = 1,
  stale = false,
}: {
  color: string;
  coreColor?: string;
  glowIntensity?: number;
  stale?: boolean;
}) {
  const pieces: THREE.BufferGeometry[] = [];
  const outline = (scale: number) => {
    const shape = new THREE.Shape();
    shape.moveTo(0, scale);
    shape.lineTo(-0.8 * scale, -scale);
    shape.lineTo(0, -0.35 * scale);
    shape.lineTo(0.8 * scale, -scale);
    shape.closePath();
    return shape;
  };
  const tint = (
    geometry: THREE.BufferGeometry,
    tintColor: string,
    alpha: number
  ) => {
    const rgb = new THREE.Color(tintColor);
    const colors = new Float32Array(
      geometry.getAttribute('position').count * 4
    );
    for (let i = 0; i < colors.length; i += 4) {
      colors.set([rgb.r, rgb.g, rgb.b, alpha], i);
    }
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 4));
    pieces.push(geometry);
  };
  const band = (outer: number, inner: number, alpha: number) => {
    const shape = outline(outer);
    shape.holes.push(outline(inner));
    tint(new THREE.ShapeGeometry(shape), color, alpha);
  };
  band(1.28, 1.15, 0.06 * glowIntensity);
  band(1.15, 1.06, 0.18 * glowIntensity);
  band(1.06, 0.82, 1);
  tint(new THREE.ShapeGeometry(outline(0.82)), coreColor, 1);
  if (stale) {
    for (let i = 0; i < 4; i++) {
      tint(
        new THREE.RingGeometry(1.38, 1.5, 6, 1, (i * Math.PI) / 2, Math.PI / 3),
        color,
        0.8
      );
    }
  }
  const geometry = mergeGeometries(pieces)!;
  for (const piece of pieces) piece.dispose();
  return {
    geometry,
    material: new THREE.MeshBasicMaterial({
      vertexColors: true,
      transparent: true,
      side: THREE.DoubleSide,
      // Visibility is gated at the anchor; a globe must not slice a screen-space glyph.
      depthTest: false,
      depthWrite: false,
      toneMapped: false,
    }),
  };
}

const screenPosition = new THREE.Vector3();
const screenTip = new THREE.Vector3();
const cameraRight = new THREE.Vector3();
const cameraUp = new THREE.Vector3();
const cameraOut = new THREE.Vector3();
const markerForward = new THREE.Vector3();
const markerRight = new THREE.Vector3();
const markerScale = new THREE.Vector3();

/** Size in CSS pixels, with reported ground track projected into the camera plane.
 * CPU matrices keep visible geometry, bounds and pointer raycasting in agreement.
 */
export function setStarMarkerChevronMatrix(
  target: THREE.Matrix4,
  position: THREE.Vector3,
  forward: THREE.Vector3 | null,
  camera: THREE.Camera,
  viewportHeight: number,
  sizePixels: number
) {
  cameraRight.setFromMatrixColumn(camera.matrixWorld, 0);
  cameraUp.setFromMatrixColumn(camera.matrixWorld, 1);
  cameraOut.setFromMatrixColumn(camera.matrixWorld, 2);
  markerForward.copy(cameraUp);
  if (forward) {
    screenPosition.copy(position).project(camera);
    screenTip
      .copy(position)
      .addScaledVector(forward, 0.01)
      .project(camera)
      .sub(screenPosition);
    const x =
      (screenTip.x * camera.projectionMatrix.elements[5]) /
      camera.projectionMatrix.elements[0];
    markerForward
      .copy(cameraRight)
      .multiplyScalar(x)
      .addScaledVector(cameraUp, screenTip.y);
    if (markerForward.lengthSq() < 1e-12) markerForward.copy(cameraUp);
    markerForward.normalize();
  }
  markerRight.copy(markerForward).cross(cameraOut).normalize();
  const depth = -screenPosition
    .copy(position)
    .applyMatrix4(camera.matrixWorldInverse).z;
  const perspective = (camera as THREE.PerspectiveCamera).isPerspectiveCamera;
  const scale =
    (sizePixels * (perspective ? Math.max(depth, 0) : 1)) /
    (Math.max(viewportHeight, 1) * camera.projectionMatrix.elements[5]);
  return target
    .makeBasis(markerRight, markerForward, cameraOut)
    .scale(markerScale.setScalar(scale))
    .setPosition(position);
}

const visibilityPoint = new THREE.Vector3();
const visibilityOrigin = new THREE.Vector3();
const visibilityRay = new THREE.Vector3();

/** Frustum and radius-two Earth occlusion for complete map-overlay markers. */
export function isStarMarkerVisible(
  point: THREE.Vector3,
  camera: THREE.Camera
): boolean {
  const clip = visibilityPoint.copy(point).project(camera);
  if (Math.abs(clip.x) > 1 || Math.abs(clip.y) > 1 || clip.z < -1 || clip.z > 1)
    return false;
  const origin = visibilityOrigin.setFromMatrixPosition(camera.matrixWorld);
  const ray = visibilityRay.copy(point).sub(origin);
  const a = ray.lengthSq(),
    b = 2 * origin.dot(ray),
    d = b * b - 4 * a * (origin.lengthSq() - 4);
  if (d < 0) return true;
  const hit = (-b - Math.sqrt(d)) / (2 * a);
  return !(hit > 0 && hit < 1 - 1e-6);
}
