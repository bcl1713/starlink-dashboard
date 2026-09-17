import * as THREE from 'three';
import type { GlobeCoordinate } from './globe-route';
import { globePosition } from './globe-coordinates';
import { ROUTE_OVERLAY_RADIUS } from './globe-render-radii';

export const CORE_COLOR = '#ffffff';
export const DEFAULT_GLOW_SIZE_PIXELS = 20;

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
  uniform float uGlowSizePixels;
  uniform float uPixelRatio;

  void main() {
    vec4 modelViewPosition = modelViewMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * modelViewPosition;
    gl_PointSize = uGlowSizePixels * uPixelRatio;
  }
`;

const haloFragmentShader = `
  uniform vec3 uColor;
  uniform float uGlowIntensity;

  void main() {
    float distanceFromCenter = distance(gl_PointCoord, vec2(0.5));
    float alpha = smoothstep(0.5, 0.0, distanceFromCenter);
    alpha *= alpha * uGlowIntensity;
    gl_FragColor = vec4(uColor * alpha, alpha);
  }
`;

export type StarMarkerHaloResources = {
  geometry: THREE.BufferGeometry;
  material: THREE.ShaderMaterial;
};

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
  const material = new THREE.ShaderMaterial({
    uniforms: {
      uColor: { value: new THREE.Color(color) },
      uGlowIntensity: { value: glowIntensity },
      uGlowSizePixels: { value: glowSizePixels },
      uPixelRatio: { value: 1 },
    },
    vertexShader: haloVertexShader,
    fragmentShader: haloFragmentShader,
    transparent: true,
    depthTest: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    toneMapped: false,
  });

  return { geometry, material };
}

export function disposeStarMarkerHaloResources({
  geometry,
  material,
}: StarMarkerHaloResources) {
  geometry.dispose();
  material.dispose();
}
