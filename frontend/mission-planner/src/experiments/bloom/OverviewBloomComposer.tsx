import { useLayoutEffect, useRef } from 'react';
import { useFrame, useThree, type RootState } from '@react-three/fiber';
import * as THREE from 'three';
import {
  createBloomPipeline,
  setRenderStatsAutoReset,
  renderExperimentFrame,
  type BloomPipeline,
} from './pipeline';
import type { BloomMode, BloomSettings } from './contracts';

export type FrameEvidence = ReturnType<BloomPipeline['dimensions']> | null;
export function OverviewBloomComposer({
  mode,
  settings,
  onFrame,
}: {
  mode: BloomMode;
  settings: BloomSettings;
  onFrame: (state: RootState, dimensions: FrameEvidence, delta: number) => void;
}) {
  const { gl, scene, camera, size, viewport } = useThree();
  const pipeline = useRef<BloomPipeline | null>(null);
  const useComposer = mode !== 'current';
  useLayoutEffect(() => {
    if (!useComposer) return;
    const active = createBloomPipeline(gl, scene, camera);
    pipeline.current = active;
    return () => {
      pipeline.current = null;
      active.dispose();
    };
  }, [gl, scene, camera, useComposer]);
  useLayoutEffect(() => {
    const buffer = gl.getDrawingBufferSize(new THREE.Vector2());
    pipeline.current?.resize(buffer.x, buffer.y, {
      maxDimension: settings.maxDimension,
    });
  }, [
    gl,
    size.width,
    size.height,
    viewport.dpr,
    settings.maxDimension,
    useComposer,
  ]);
  useLayoutEffect(() => {
    pipeline.current?.configure(mode, settings);
  }, [mode, settings, useComposer]);
  // A positive priority disables R3F's automatic renderer for all three modes.
  // Camera, controls and simulation run first; exactly one owner then renders.
  useFrame((state, delta) => {
    gl.info.reset();

    renderExperimentFrame(mode, gl, scene, camera, pipeline.current, delta);
    onFrame(state, pipeline.current?.dimensions() ?? null, delta);
  }, 1);
  useLayoutEffect(() => {
    const previous = gl.info.autoReset;
    setRenderStatsAutoReset(gl, false);
    return () => {
      setRenderStatsAutoReset(gl, previous);
    };
  }, [gl]);
  return null;
}
