import { Line } from '@react-three/drei';
import { useFrame } from '@react-three/fiber';
import { useEffect, useMemo } from 'react';
import * as THREE from 'three';
import {
  createAnimatedFlowResources,
  disposeAnimatedFlowResources,
  FlowParticlePool,
  prepareFlowPath,
  type FlowEmitterConfig,
  type FlowPoint,
  writeFlowParticles,
} from './overview-animated-flow-line-rendering';

export interface FlowLineLayer {
  color: string;
  linewidth: number;
  opacity: number;
  blending?: THREE.Blending;
}

export interface AnimatedFlowLineProps {
  points: readonly FlowPoint[];
  outer?: FlowLineLayer;
  glow?: FlowLineLayer;
  core?: FlowLineLayer;
  depthTest?: boolean;
  depthWrite?: boolean;
  forward?: FlowEmitterConfig;
  reverse?: FlowEmitterConfig;
  random?: () => number;
}

const DEFAULT_OUTER: FlowLineLayer = {
  color: '#ffb000',
  linewidth: 10,
  opacity: 0.055,
  blending: THREE.NormalBlending,
};
const DEFAULT_GLOW: FlowLineLayer = {
  color: '#ffb000',
  linewidth: 5,
  opacity: 0.12,
  blending: THREE.NormalBlending,
};
const DEFAULT_CORE: FlowLineLayer = {
  color: '#fff1c0',
  linewidth: 1,
  opacity: 0.7,
  blending: THREE.NormalBlending,
};
const DISABLED_EMITTER: FlowEmitterConfig = {
  enabled: false,
  rate: 0,
  speed: 0,
  color: '#ffffff',
  size: 1,
  brightness: 0,
  maxParticles: 0,
};

export function AnimatedFlowLine({
  points,
  outer = DEFAULT_OUTER,
  glow = DEFAULT_GLOW,
  core = DEFAULT_CORE,
  depthTest = true,
  depthWrite = false,
  forward,
  reverse,
  random,
}: AnimatedFlowLineProps) {
  const capacity = (forward?.maxParticles ?? 0) + (reverse?.maxParticles ?? 0);
  const pool = useMemo(() => new FlowParticlePool({ random }), [random]);
  const path = useMemo(() => prepareFlowPath(points), [points]);
  const resources = useMemo(
    () => createAnimatedFlowResources(Math.max(1, capacity)),
    [capacity]
  );

  useEffect(() => {
    pool.configure(forward ?? DISABLED_EMITTER, reverse ?? DISABLED_EMITTER);
  }, [forward, pool, reverse]);

  useEffect(() => {
    resources.material.depthTest = depthTest;
    resources.material.depthWrite = depthWrite;
  }, [depthTest, depthWrite, resources]);

  useEffect(() => {
    return () => disposeAnimatedFlowResources(resources);
  }, [resources]);

  useFrame((state, delta) => {
    if (path.points.length < 2) {
      resources.geometry.setDrawRange(0, 0);
      return;
    }

    const pixelRatio = state.gl.getPixelRatio();
    resources.material.uniforms.uPixelRatio.value = pixelRatio;
    resources.material.uniforms.uViewportHeightPixels.value =
      state.size.height * pixelRatio;
    pool.update(delta);
    writeFlowParticles(resources, path, pool.snapshot());
  });

  if (points.length < 2) return null;

  const depthOffsetProps = {
    polygonOffset: true,
    polygonOffsetFactor: -1,
    polygonOffsetUnits: -2,
  };

  return (
    <group>
      <Line
        points={points}
        color={outer.color}
        linewidth={outer.linewidth}
        transparent
        opacity={outer.opacity}
        blending={outer.blending ?? THREE.AdditiveBlending}
        toneMapped={false}
        depthTest={depthTest}
        depthWrite={depthWrite}
        {...depthOffsetProps}
      />
      <Line
        points={points}
        color={glow.color}
        linewidth={glow.linewidth}
        transparent
        opacity={glow.opacity}
        blending={glow.blending ?? THREE.AdditiveBlending}
        toneMapped={false}
        depthTest={depthTest}
        depthWrite={depthWrite}
        {...depthOffsetProps}
      />
      <Line
        points={points}
        color={core.color}
        linewidth={core.linewidth}
        transparent
        opacity={core.opacity}
        blending={core.blending ?? THREE.NormalBlending}
        toneMapped={false}
        depthTest={depthTest}
        depthWrite={depthWrite}
        {...depthOffsetProps}
      />
      <primitive object={resources.points} />
    </group>
  );
}
