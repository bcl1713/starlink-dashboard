import { useLayoutEffect, useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { MAX_OBJECTS, type OrbitalSnapshot } from './types';
import {
  createSpriteResources,
  disposeSpriteResources,
  writeSpriteSnapshots,
  type SpriteResources,
} from './sprite-resources';

export function OrbitalSprites({
  previous,
  current,
  generation,
  reducedMotion,
}: {
  previous: OrbitalSnapshot | null;
  current: OrbitalSnapshot | null;
  generation: number;
  reducedMotion: boolean;
}) {
  const group = useMemo(() => new THREE.Group(), []);
  const resources = useRef<SpriteResources | null>(null);
  const elapsed = useRef(0);
  useLayoutEffect(() => {
    const active = createSpriteResources(MAX_OBJECTS);
    resources.current = active;
    group.add(active.points);
    return () => {
      resources.current = null;
      group.remove(active.points);
      disposeSpriteResources(active);
    };
  }, [group, generation]);
  useLayoutEffect(() => {
    if (!resources.current) return;
    writeSpriteSnapshots(resources.current, previous, current, generation);
    elapsed.current = 0;
    resources.current.material.uniforms.mixAmount.value =
      reducedMotion || !previous ? 1 : 0;
  }, [current, previous, generation, reducedMotion]);
  useFrame((_, delta) => {
    const active = resources.current;
    if (!active) return;
    elapsed.current = Math.min(1, elapsed.current + delta);
    active.material.uniforms.mixAmount.value =
      reducedMotion || !previous ? 1 : elapsed.current;
  });
  return <primitive object={group} dispose={null} />;
}
