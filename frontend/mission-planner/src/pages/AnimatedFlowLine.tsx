import { Line } from '@react-three/drei';
import { useFrame } from '@react-three/fiber';
import { useEffect, useMemo } from 'react';
import {
  createAnimatedFlowResources,
  disposeAnimatedFlowResources,
  FlowParticlePool,
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
  linewidth: 7,
  opacity: 0.1,
};
const DEFAULT_GLOW: FlowLineLayer = {
  color: '#ffb000',
  linewidth: 4,
  opacity: 0.24,
};
const DEFAULT_CORE: FlowLineLayer = {
  color: '#ffb000',
  linewidth: 1.5,
  opacity: 0.9,
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
  const pool = useMemo(
    () => new FlowParticlePool({ points, random }),
    [points, random]
  );
  const resources = useMemo(
    () => createAnimatedFlowResources(Math.max(1, capacity * 4)),
    [capacity]
  );

  useEffect(() => {
    if (forward) pool.configure(forward, reverse);
  }, [forward, pool, reverse]);

  useEffect(() => {
    return () => disposeAnimatedFlowResources(resources);
  }, [resources]);

  useFrame((_, delta) => {
    pool.update(delta);
    writeFlowParticles(resources, points, pool.snapshot());
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
        depthTest={depthTest}
        depthWrite={depthWrite}
      />
      <Line
        points={points}
        color={glow.color}
        linewidth={glow.linewidth}
        transparent
        opacity={glow.opacity}
        depthTest={depthTest}
        depthWrite={depthWrite}
      />
      <Line
        points={points}
        color={core.color}
        linewidth={core.linewidth}
        transparent
        opacity={core.opacity}
        depthTest={depthTest}
        depthWrite={depthWrite}
      />
      <primitive object={resources.points} />
    </group>
  );
}
