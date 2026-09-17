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
};
const DEFAULT_GLOW: FlowLineLayer = {
  color: '#ffb000',
  linewidth: 5,
  opacity: 0.12,
};
const DEFAULT_CORE: FlowLineLayer = {
  color: '#fff1c0',
  linewidth: 1,
  opacity: 0.7,
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

    resources.material.uniforms.uPixelRatio.value = state.gl.getPixelRatio();
    pool.update(delta);
    writeFlowParticles(resources, path, pool.snapshot());
  });

  if (points.length < 2) return null;

  return (
    <group>
      <Line
        points={points}
        color={outer.color}
        linewidth={outer.linewidth}
        transparent
        opacity={outer.opacity}
        blending={THREE.AdditiveBlending}
        toneMapped={false}
        depthTest={depthTest}
        depthWrite={depthWrite}
      />
      <Line
        points={points}
        color={glow.color}
        linewidth={glow.linewidth}
        transparent
        opacity={glow.opacity}
        blending={THREE.AdditiveBlending}
        toneMapped={false}
        depthTest={depthTest}
        depthWrite={depthWrite}
      />
      <Line
        points={points}
        color={core.color}
        linewidth={core.linewidth}
        transparent
        opacity={core.opacity}
        toneMapped={false}
        depthTest={depthTest}
        depthWrite={depthWrite}
      />
      <primitive object={resources.points} />
    </group>
  );
}
