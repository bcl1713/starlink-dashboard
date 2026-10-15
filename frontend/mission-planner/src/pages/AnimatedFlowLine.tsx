import { useFrame } from '@react-three/fiber';
import {
  useCallback,
  useLayoutEffect,
  useMemo,
  useRef,
  useSyncExternalStore,
  type RefObject,
} from 'react';
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion';
import * as THREE from 'three';
import {
  GlobeRouteRibbon,
  type GlobeRouteRibbonLayer,
} from './GlobeRouteRibbon';
import {
  createAnimatedFlowResources,
  createFlowLineResources,
  disposeFlowLineResources,
  type FlowLineResources,
  disposeAnimatedFlowResources,
  FlowParticlePool,
  prepareFlowPath,
  setAnimatedFlowViewport,
  type AnimatedFlowResources,
  type PreparedFlowPath,
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
  canAnimate?: () => boolean;
  /** Keep in-flight progress on a moving path; change this for a new link. */
  particleKey?: string;
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

function FlowLine({
  points,
  layer,
  depthTest,
  depthWrite,
  fallbackBlending = THREE.AdditiveBlending,
}: {
  points: readonly FlowPoint[];
  layer: FlowLineLayer;
  depthTest: boolean;
  depthWrite: boolean;
  fallbackBlending?: THREE.Blending;
}) {
  const group = useMemo(() => new THREE.Group(), []);
  const resources = useRef<FlowLineResources | null>(null);
  useLayoutEffect(() => {
    const active = createFlowLineResources(points, {
      color: layer.color,
      linewidth: layer.linewidth,
      opacity: layer.opacity,
      blending: layer.blending ?? fallbackBlending,
      transparent: true,
      toneMapped: false,
      depthTest,
      depthWrite,
      polygonOffset: true,
      polygonOffsetFactor: -1,
      polygonOffsetUnits: -2,
    });
    resources.current = active;
    group.add(active.line);
    return () => {
      resources.current = null;
      group.remove(active.line);
      disposeFlowLineResources(active);
    };
  }, [depthTest, depthWrite, fallbackBlending, group, layer, points]);
  useFrame((state) => {
    resources.current?.material.resolution.set(
      state.size.width,
      state.size.height
    );
  });
  return <primitive object={group} dispose={null} />;
}

function pageHidden() {
  return document.hidden;
}

interface ParticleBranch {
  pool: FlowParticlePool;
  resources: AnimatedFlowResources;
}

function FlowParticles({
  path,
  forward,
  reverse,
  random,
  depthTest,
  depthWrite,
  canAnimate,
  particleKey,
  discardDeltaRef,
}: Pick<
  AnimatedFlowLineProps,
  'forward' | 'reverse' | 'random' | 'canAnimate' | 'particleKey'
> & {
  path: PreparedFlowPath;
  depthTest: boolean;
  depthWrite: boolean;
  discardDeltaRef: RefObject<boolean>;
}) {
  const capacity = (forward?.maxParticles ?? 0) + (reverse?.maxParticles ?? 0);
  const group = useMemo(() => new THREE.Group(), []);
  const branch = useRef<ParticleBranch | null>(null);
  const eligibility = useRef(canAnimate);
  const resetKey = particleKey ?? path;

  const release = useCallback(() => {
    const active = branch.current;
    if (!active) return;
    branch.current = null;
    active.pool.clear();
    active.resources.geometry.setDrawRange(0, 0);
    group.remove(active.resources.points);
    disposeAnimatedFlowResources(active.resources);
  }, [group]);

  const allocate = useCallback(() => {
    const active = {
      pool: new FlowParticlePool({ random }),
      resources: createAnimatedFlowResources(Math.max(1, capacity), {
        depthTest,
        depthWrite,
      }),
    };
    branch.current = active;
    group.add(active.resources.points);
    return active;
  }, [capacity, depthTest, depthWrite, group, random]);

  useLayoutEffect(() => {
    eligibility.current = canAnimate;
    if (canAnimate && !canAnimate()) release();
  }, [canAnimate, release]);

  // Allocate inside setup: StrictMode cleanup must never leave a disposed
  // geometry in the next setup. The primitive's empty group owns no GPU data.
  useLayoutEffect(() => {
    if (!eligibility.current || eligibility.current()) allocate();
    return release;
  }, [allocate, release, resetKey]);

  useLayoutEffect(() => {
    const active = branch.current;
    if (!active) return;
    active.pool.configure(
      forward ?? DISABLED_EMITTER,
      reverse ?? DISABLED_EMITTER
    );
    if (active.pool.snapshot().length === 0) {
      active.resources.geometry.setDrawRange(0, 0);
    } else {
      writeFlowParticles(active.resources, path, active.pool.snapshot());
    }
  }, [allocate, forward, path, resetKey, reverse]);

  useFrame((state, delta) => {
    if (document.hidden || (canAnimate && !canAnimate())) {
      release();
      discardDeltaRef.current = true;
      return;
    }
    let active = branch.current;
    if (!active) {
      active = allocate();
      active.pool.configure(
        forward ?? DISABLED_EMITTER,
        reverse ?? DISABLED_EMITTER
      );
      discardDeltaRef.current = true;
    }
    if (discardDeltaRef.current) {
      discardDeltaRef.current = false;
      return;
    }
    const pixelRatio = state.gl.getPixelRatio();
    setAnimatedFlowViewport(
      active.resources,
      pixelRatio,
      state.size.height * pixelRatio
    );
    active.pool.update(Math.min(delta, 0.1), path.totalLength);
    writeFlowParticles(active.resources, path, active.pool.snapshot());
  });

  return <primitive object={group} dispose={null} />;
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
  canAnimate,
  particleKey,
}: AnimatedFlowLineProps) {
  const reducedMotion = usePrefersReducedMotion();
  const discardDeltaRef = useRef(pageHidden());
  const subscribeVisibility = useCallback((notify: () => void) => {
    const onVisibility = () => {
      if (document.hidden) discardDeltaRef.current = true;
      notify();
    };
    document.addEventListener('visibilitychange', onVisibility);
    return () => document.removeEventListener('visibilitychange', onVisibility);
  }, []);
  const hidden = useSyncExternalStore(
    subscribeVisibility,
    pageHidden,
    () => false
  );
  const path = useMemo(() => prepareFlowPath(points), [points]);
  const layers = useMemo(
    () => ({
      outer: ribbonLayer(outer, 0.05),
      glow: ribbonLayer(glow, 0.028),
      core: ribbonLayer(core, 0.012),
    }),
    [outer, glow, core]
  );
  const validPath =
    points.length >= 2 &&
    Number.isFinite(path.totalLength) &&
    path.totalLength > 0;

  if (!validPath) return null;

  const useContinuousRibbon = points.length > 2;

  return (
    <group>
      {showLine && useContinuousRibbon && (
        <GlobeRouteRibbon points={points} {...layers} depthTest={depthTest} />
      )}
      {showLine && !useContinuousRibbon && (
        <>
          <FlowLine
            points={points}
            layer={outer}
            depthTest={depthTest}
            depthWrite={depthWrite}
          />
          <FlowLine
            points={points}
            layer={glow}
            depthTest={depthTest}
            depthWrite={depthWrite}
          />
          <FlowLine
            points={points}
            layer={core}
            fallbackBlending={THREE.NormalBlending}
            depthTest={depthTest}
            depthWrite={depthWrite}
          />
        </>
      )}
      {!hidden && !reducedMotion && (forward?.enabled || reverse?.enabled) && (
        <FlowParticles
          path={path}
          forward={forward}
          reverse={reverse}
          random={random}
          depthTest={depthTest}
          depthWrite={depthWrite}
          canAnimate={canAnimate}
          particleKey={particleKey}
          discardDeltaRef={discardDeltaRef}
        />
      )}
    </group>
  );
}
