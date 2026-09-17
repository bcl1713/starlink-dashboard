import { useFrame } from '@react-three/fiber';
import { useEffect, useMemo } from 'react';
import * as THREE from 'three';
import type { FlowPoint } from './overview-animated-flow-line-rendering';

export interface GlobeRouteRibbonLayer {
  color: string;
  widthPixels: number;
  maxWorldWidth: number;
  opacity: number;
  blending?: THREE.Blending;
}

export interface GlobeRouteRibbonProps {
  points: readonly FlowPoint[];
  outer?: GlobeRouteRibbonLayer;
  glow?: GlobeRouteRibbonLayer;
  core?: GlobeRouteRibbonLayer;
  depthTest?: boolean;
}

const DEFAULT_OUTER: GlobeRouteRibbonLayer = {
  color: '#ff9d00',
  widthPixels: 8,
  maxWorldWidth: 0.05,
  opacity: 0.12,
  blending: THREE.AdditiveBlending,
};

const DEFAULT_GLOW: GlobeRouteRibbonLayer = {
  color: '#ffb000',
  widthPixels: 4,
  maxWorldWidth: 0.028,
  opacity: 0.3,
  blending: THREE.AdditiveBlending,
};

const DEFAULT_CORE: GlobeRouteRibbonLayer = {
  color: '#ffd86b',
  widthPixels: 1.25,
  maxWorldWidth: 0.012,
  opacity: 0.95,
  blending: THREE.NormalBlending,
};

const ribbonVertexShader = `
  uniform float uHalfWidthWorld;
  uniform float uDepthBias;
  attribute vec3 aSide;

  void main() {
    vec3 displaced = position + aSide * uHalfWidthWorld;
    vec4 mvPosition = modelViewMatrix * vec4(displaced, 1.0);
    gl_Position = projectionMatrix * mvPosition;
    gl_Position.z -= uDepthBias * gl_Position.w;
  }
`;

const ribbonFragmentShader = `
  uniform vec3 uColor;
  uniform float uOpacity;

  void main() {
    gl_FragColor = vec4(uColor, uOpacity);
  }
`;

function fallbackSide(normal: THREE.Vector3, target: THREE.Vector3) {
  const axis = Math.abs(normal.y) < 0.9
    ? new THREE.Vector3(0, 1, 0)
    : new THREE.Vector3(1, 0, 0);
  return target.crossVectors(normal, axis).normalize();
}

export function createGlobeRouteRibbonGeometry(
  points: readonly FlowPoint[]
): THREE.BufferGeometry {
  const geometry = new THREE.BufferGeometry();
  if (points.length < 2) return geometry;

  const positions = new Float32Array(points.length * 2 * 3);
  const sides = new Float32Array(points.length * 2 * 3);
  const indices = new Uint32Array((points.length - 1) * 6);

  const previous = new THREE.Vector3();
  const current = new THREE.Vector3();
  const next = new THREE.Vector3();
  const tangent = new THREE.Vector3();
  const normal = new THREE.Vector3();
  const side = new THREE.Vector3();

  for (let index = 0; index < points.length; index += 1) {
    const point = points[index];
    current.set(point[0], point[1], point[2]);

    if (index === 0) {
      previous.copy(current).sub(
        next
          .set(points[1][0], points[1][1], points[1][2])
          .sub(current)
      );
    } else {
      const source = points[index - 1];
      previous.set(source[0], source[1], source[2]);
    }

    if (index === points.length - 1) {
      next.copy(current).add(
        tangent.copy(current).sub(previous)
      );
    } else {
      const source = points[index + 1];
      next.set(source[0], source[1], source[2]);
    }

    tangent.copy(next).sub(previous).normalize();
    normal.copy(current).normalize();
    side.crossVectors(normal, tangent);

    if (side.lengthSq() < 1e-10) {
      fallbackSide(normal, side);
    } else {
      side.normalize();
    }

    for (let sideIndex = 0; sideIndex < 2; sideIndex += 1) {
      const sign = sideIndex === 0 ? -1 : 1;
      const vertexIndex = index * 2 + sideIndex;
      const offset = vertexIndex * 3;
      positions[offset] = current.x;
      positions[offset + 1] = current.y;
      positions[offset + 2] = current.z;
      sides[offset] = side.x * sign;
      sides[offset + 1] = side.y * sign;
      sides[offset + 2] = side.z * sign;
    }
  }

  for (let index = 0; index < points.length - 1; index += 1) {
    const left = index * 2;
    const right = left + 1;
    const nextLeft = left + 2;
    const nextRight = left + 3;
    const offset = index * 6;

    indices[offset] = left;
    indices[offset + 1] = right;
    indices[offset + 2] = nextLeft;
    indices[offset + 3] = right;
    indices[offset + 4] = nextRight;
    indices[offset + 5] = nextLeft;
  }

  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('aSide', new THREE.BufferAttribute(sides, 3));
  geometry.setIndex(new THREE.BufferAttribute(indices, 1));
  geometry.computeBoundingSphere();
  return geometry;
}

function createRibbonMaterial(
  layer: GlobeRouteRibbonLayer,
  depthTest: boolean
) {
  return new THREE.ShaderMaterial({
    uniforms: {
      uColor: { value: new THREE.Color(layer.color) },
      uOpacity: { value: layer.opacity },
      uHalfWidthWorld: { value: 0 },
      uDepthBias: { value: 0.00001 },
    },
    vertexShader: ribbonVertexShader,
    fragmentShader: ribbonFragmentShader,
    transparent: layer.opacity < 1,
    depthTest,
    depthWrite: false,
    blending: layer.blending ?? THREE.NormalBlending,
    side: THREE.DoubleSide,
    toneMapped: false,
  });
}

function nearestPointDistance(
  camera: THREE.Camera,
  points: readonly FlowPoint[]
) {
  let nearest = Number.POSITIVE_INFINITY;
  const scratch = new THREE.Vector3();

  for (const point of points) {
    scratch.set(point[0], point[1], point[2]);
    nearest = Math.min(nearest, camera.position.distanceTo(scratch));
  }

  return nearest;
}

function updateLayerWidth(
  material: THREE.ShaderMaterial,
  layer: GlobeRouteRibbonLayer,
  camera: THREE.Camera,
  viewportHeight: number,
  distance: number
) {
  if (!(camera instanceof THREE.PerspectiveCamera) || viewportHeight <= 0) {
    material.uniforms.uHalfWidthWorld.value = layer.maxWorldWidth / 2;
    return;
  }

  const visibleHeight =
    2 * distance * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2);
  const worldPerPixel = visibleHeight / viewportHeight;
  const targetWorldWidth = layer.widthPixels * worldPerPixel;
  const width = Math.min(layer.maxWorldWidth, targetWorldWidth);
  material.uniforms.uHalfWidthWorld.value = width / 2;
}

export function GlobeRouteRibbon({
  points,
  outer = DEFAULT_OUTER,
  glow = DEFAULT_GLOW,
  core = DEFAULT_CORE,
  depthTest = true,
}: GlobeRouteRibbonProps) {
  const geometry = useMemo(
    () => createGlobeRouteRibbonGeometry(points),
    [points]
  );
  const outerMaterial = useMemo(
    () => createRibbonMaterial(outer, depthTest),
    [depthTest, outer]
  );
  const glowMaterial = useMemo(
    () => createRibbonMaterial(glow, depthTest),
    [depthTest, glow]
  );
  const coreMaterial = useMemo(
    () => createRibbonMaterial(core, depthTest),
    [core, depthTest]
  );

  useEffect(() => {
    return () => {
      geometry.dispose();
      outerMaterial.dispose();
      glowMaterial.dispose();
      coreMaterial.dispose();
    };
  }, [coreMaterial, geometry, glowMaterial, outerMaterial]);

  useFrame((state) => {
    if (points.length < 2) return;
    const distance = nearestPointDistance(state.camera, points);
    updateLayerWidth(
      outerMaterial,
      outer,
      state.camera,
      state.size.height,
      distance
    );
    updateLayerWidth(
      glowMaterial,
      glow,
      state.camera,
      state.size.height,
      distance
    );
    updateLayerWidth(
      coreMaterial,
      core,
      state.camera,
      state.size.height,
      distance
    );
  });

  if (points.length < 2) return null;

  return (
    <group>
      <mesh geometry={geometry} material={outerMaterial} renderOrder={1} />
      <mesh geometry={geometry} material={glowMaterial} renderOrder={2} />
      <mesh geometry={geometry} material={coreMaterial} renderOrder={3} />
    </group>
  );
}
