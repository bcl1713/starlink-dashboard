import { useLayoutEffect, useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { INITIAL_CAMERA } from './scenario';

export function CameraReplay({
  epoch,
  path,
  paused,
}: {
  epoch: number;
  path: boolean;
  paused: boolean;
}) {
  const { camera, gl } = useThree();
  const controls = useRef<OrbitControls | null>(null);
  const frame = useRef(0);
  useLayoutEffect(() => {
    const instance = new OrbitControls(camera, gl.domElement);
    instance.minDistance = 2.15;
    instance.maxDistance = 14;
    controls.current = instance;
    return () => {
      controls.current = null;
      instance.dispose();
    };
  }, [camera, gl]);
  useLayoutEffect(() => {
    frame.current = 0;
    camera.position.set(...INITIAL_CAMERA);
    camera.lookAt(0, 0, 0);
    controls.current?.target.set(0, 0, 0);
    controls.current?.update();
  }, [epoch, camera]);
  useFrame(() => {
    if (controls.current) controls.current.enabled = !path;
    if (!path || paused) return;
    const t = (frame.current++ / 600) * Math.PI * 2;
    // A fixed frame-index path makes geometry and camera workload replayable.
    const distance = 6.8 + 1.2 * Math.sin(t * 2);
    camera.position.set(
      Math.sin(t) * distance,
      2 + Math.sin(t) * 0.5,
      Math.cos(t) * distance
    );
    camera.lookAt(0, 0, 0);
  });
  return null;
}
