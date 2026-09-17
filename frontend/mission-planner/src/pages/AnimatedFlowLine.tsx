import { Line } from '@react-three/drei';
import { useFrame } from '@react-three/fiber';
import { useEffect, useMemo } from 'react';
import * as THREE from 'three';
import {
  GlobeRouteRibbon,
  type GlobeRouteRibbonLayer,
} from './GlobeRouteRibbon';
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
  maxWorldWidth?: number;
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
  showLine?: boolean;
}

const DEFAULT_OUTER: FlowLineLayer = {
  color: '#ffb000',
  linewidth: 8,
  opacity: 0.12,
  blending: THREE.AdditiveBlending,
  maxWorldWidth: 0.05,
};
const DEFAULT_GLOW: FlowLineLayer = {
  color: '#ffb000',
  linewidth: 4,
  opacity: 0.3,
  blending: THREE.AdditiveBlending,
  maxWorldWidth: 0.028,
};
const DEFAULT_CORE: FlowLineLayer = {
  color: '#ffd86b',
  linewidth: 1.25,
  opacity: 0.95,
  blending: THREE.NormalBlending,
  maxWorldWidth: 0.012,
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

function ribbonLayer(
  layer: FlowLineLayer,
  fallbackWorldWidth: number
): GlobeRouteRibbonLayer {
  return {
    color: layer.color,
    widthPixels: layer.linewidth,
    maxWorldWidth: layer.maxWorldWidth ?? fallbackWorldWidth,
    opacity: layer.opacity,
    blending: layer.blending,
  };
}

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
  showLine = true,
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
    if (path.points.length < 2 || path.totalLength <= 0) {
      resources.geometry.setDrawRange(0, 0);
      return;
    }

    const pixelRatio = state.gl.getPixelRatio();
    resources.material.uniforms.uPixelRatio.value = pixelRatio;
    resources.material.uniforms.uViewportHeightPixels.value =
      state.size.height * pixelRatio;
    pool.update(delta, path.totalLength);
    writeFlowParticles(resources, path, pool.snapshot());
  });

  if (points.length < 2) return null;

  const depthOffsetProps = {
    polygonOffset: true,
    polygonOffsetFactor: -1,
    polygonOffsetUnits: -2,
  };

  const useContinuousRibbon = points.length > 2;

  return (
    <group>
      {showLine && useContinuousRibbon && (
        <GlobeRouteRibbon
          points={points}
          outer={ribbonLayer(outer, 0.05)}
          glow={ribbonLayer(glow, 0.028)}
          core={ribbonLayer(core, 0.012)}
          depthTest={depthTest}
        />
      )}
      {showLine && !useContinuousRibbon && (
        <>
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
        </>
      )}
      <primitive object={resources.points} />
    </group>
  );
}
