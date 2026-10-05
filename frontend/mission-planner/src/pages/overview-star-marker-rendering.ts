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
    alpha: number | ((x: number, y: number) => number),
    glow = false
  ) => {
    const rgb = new THREE.Color(tintColor);
    const positions = geometry.getAttribute('position');
    const colors = new Float32Array(positions.count * 4);
    for (let i = 0; i < colors.length; i += 4) {
      const opacity =
        typeof alpha === 'number'
          ? alpha
          : alpha(positions.getX(i / 4), positions.getY(i / 4));
      colors.set([rgb.r, rgb.g, rgb.b, opacity], i);
    }
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 4));
    geometry.setAttribute(
      'markerGlow',
      new THREE.Float32BufferAttribute(
        new Float32Array(positions.count).fill(glow ? 1 : 0),
        1
      )
    );
    pieces.push(geometry);
  };
  const band = (
    outer: number,
    inner: number,
    outerAlpha: number,
    innerAlpha: number,
    glow = false
  ) => {
    const shape = outline(outer);
    shape.holes.push(outline(inner));
    tint(
      new THREE.ShapeGeometry(shape),
      color,
      (x, y) => {
        // Each contour vertex belongs to one homothetic chevron outline.
        const scale =
          Math.abs(x) > 1e-6 ? Math.abs(x) / 0.8 : y < 0 ? -y / 0.35 : y;
        const t = THREE.MathUtils.clamp(
          (scale - inner) / (outer - inner),
          0,
          1
        );
        return THREE.MathUtils.lerp(innerAlpha, outerAlpha, t);
      },
      glow
    );
  };
  const intensity = Math.max(0, glowIntensity);
  band(3, 1.7, 0, 0.35 * intensity, true);
  band(1.7, 1.06, 0.35 * intensity, 0.9 * intensity, true);
  band(1.06, 0.82, 1, 1);
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
  const material = new THREE.MeshBasicMaterial({
    vertexColors: true,
    transparent: true,
    side: THREE.DoubleSide,
    forceSinglePass: true,
    // Alpha-zero premultiplied halo fragments add light; the solid body retains normal coverage.
    premultipliedAlpha: true,
    blending: THREE.CustomBlending,
    blendSrc: THREE.OneFactor,
    blendDst: THREE.OneMinusSrcAlphaFactor,
    // Visibility is gated at the anchor; a globe must not slice a screen-space glyph.
    depthTest: false,
    depthWrite: false,
    toneMapped: false,
  });
  material.onBeforeCompile = (shader) => {
    shader.vertexShader = `attribute float markerGlow;
varying float vMarkerGlow;
${shader.vertexShader}`.replace(
      '#include <begin_vertex>',
      `#include <begin_vertex>
vMarkerGlow = markerGlow;`
    );
    shader.fragmentShader = `varying float vMarkerGlow;
${shader.fragmentShader}`.replace(
      '#include <premultiplied_alpha_fragment>',
      `#include <premultiplied_alpha_fragment>
if (vMarkerGlow > 0.5) gl_FragColor.a = 0.0;`
    );
  };
  return { geometry, material };
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

/** Telemetry heading is clockwise from geographic north in the local globe tangent plane. */
export function starMarkerHeadingDirection(
  position: readonly [number, number, number],
  headingDegrees: number | undefined
): THREE.Vector3 | null {
  if (typeof headingDegrees !== 'number' || !Number.isFinite(headingDegrees))
    return null;
  const latitude = Math.atan2(
    position[1],
    Math.hypot(position[0], position[2])
  );
  const longitude = Math.atan2(-position[2], position[0]);
  const heading = THREE.MathUtils.degToRad(headingDegrees);
  return new THREE.Vector3(
    -Math.sin(latitude) * Math.cos(longitude),
    Math.cos(latitude),
    Math.sin(latitude) * Math.sin(longitude)
  )
    .multiplyScalar(Math.cos(heading))
    .addScaledVector(
      new THREE.Vector3(-Math.sin(longitude), 0, -Math.cos(longitude)),
      Math.sin(heading)
    );
}

/** Keep the luminous halo decorative: pointer hits belong to the body or stale ring. */
export function raycastStarMarkerChevron(
  this: THREE.Mesh,
  raycaster: THREE.Raycaster,
  intersections: THREE.Intersection[]
) {
  const start = intersections.length;
  if ((this as THREE.InstancedMesh).isInstancedMesh) {
    THREE.InstancedMesh.prototype.raycast.call(this, raycaster, intersections);
  } else {
    THREE.Mesh.prototype.raycast.call(this, raycaster, intersections);
  }
  const glow = this.geometry.getAttribute('markerGlow');
  let next = start;
  for (let i = start; i < intersections.length; i++) {
    const hit = intersections[i];
    if (hit.face && glow.getX(hit.face.a) > 0.5) continue;
    intersections[next++] = hit;
  }
  intersections.length = next;
}
