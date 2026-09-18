import * as THREE from 'three';
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
