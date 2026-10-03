import { useFrame } from '@react-three/fiber';
import { useLayoutEffect, useMemo, useRef } from 'react';
import * as THREE from 'three';
import { createGlobeRouteRibbonGeometry } from './globe-route-ribbon-geometry';
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
  points: readonly FlowPoint[],
  scratch: THREE.Vector3
) {
  let nearest = Number.POSITIVE_INFINITY;

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
  const group = useMemo(() => new THREE.Group(), []);
  const resources = useRef<{
    outerMaterial: THREE.ShaderMaterial;
    glowMaterial: THREE.ShaderMaterial;
    coreMaterial: THREE.ShaderMaterial;
  } | null>(null);
  const distanceScratch = useMemo(() => new THREE.Vector3(), []);

  useLayoutEffect(() => {
    if (points.length < 2) return;
    const geometry = createGlobeRouteRibbonGeometry(points);
    const outerMaterial = createRibbonMaterial(outer, depthTest);
    const glowMaterial = createRibbonMaterial(glow, depthTest);
    const coreMaterial = createRibbonMaterial(core, depthTest);
    resources.current = { outerMaterial, glowMaterial, coreMaterial };
    const meshes = [outerMaterial, glowMaterial, coreMaterial].map(
      (material, index) => {
        const mesh = new THREE.Mesh(geometry, material);
        mesh.renderOrder = index + 1;
        return mesh;
      }
    );
    group.add(...meshes);

    return () => {
      resources.current = null;
      group.remove(...meshes);
      geometry.dispose();
      outerMaterial.dispose();
      glowMaterial.dispose();
      coreMaterial.dispose();
    };
  }, [core, depthTest, glow, group, outer, points]);

  useFrame((state) => {
    const active = resources.current;
    if (!active) return;
    const { outerMaterial, glowMaterial, coreMaterial } = active;
    const distance = nearestPointDistance(
      state.camera,
      points,
      distanceScratch
    );
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

  return <primitive object={group} dispose={null} />;
}
