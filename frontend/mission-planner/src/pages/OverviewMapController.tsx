import { useEffect, useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import { PerspectiveCamera, Quaternion, Vector3 } from 'three';
import { globePosition } from './globe-coordinates';
import {
  overviewCameraFrame,
  overviewInitialDirection,
  type OverviewCameraIntent,
} from './overview-camera-frame';
import type {
  OverviewLayoutMode,
  OverviewSafeRect,
} from './overview-responsive-layout';
import type { GlobeCoordinate } from './globe-route';
interface Props {
  mode: OverviewLayoutMode;
  safeRect: OverviewSafeRect;
  exploring: boolean;
  intent: OverviewCameraIntent;
  aircraft: GlobeCoordinate | null;
  followAvailable: boolean;
  reducedMotion: boolean;
  route: readonly [number, number, number][];
  initialReady: boolean;
  resetRevision: number;
  onManual: () => void;
  onCameraSettled: () => void;
}
export function OverviewMapController({
  mode,
  safeRect,
  exploring,
  intent,
  aircraft,
  followAvailable,
  reducedMotion,
  route,
  initialReady,
  resetRevision,
  onManual,
  onCameraSettled,
}: Props) {
  const camera = useThree((state) => state.camera);
  const size = useThree((state) => state.size);
  const gl = useThree((state) => state.gl);
  const controls = useRef<OrbitControlsImpl>(null);
  const fitted = useRef<{
    mode: OverviewLayoutMode;
    width: number;
    height: number;
    safeRect: OverviewSafeRect;
    intent: OverviewCameraIntent;
    resetRevision: number;
  } | null>(null);
  const settleTimer = useRef<ReturnType<typeof setTimeout> | undefined>(
    undefined
  );
  const transition = useRef<{
    elapsed: number;
    fromQuaternion: Quaternion;
    toQuaternion: Quaternion;
    fromDistance: number;
    toDistance: number;
    fromOffsetX: number;
    fromOffsetY: number;
    toOffsetX: number;
    toOffsetY: number;
  } | null>(null);
  useFrame((_, delta) => {
    const tween = transition.current;
    if (!tween || !(camera instanceof PerspectiveCamera)) return;
    tween.elapsed = reducedMotion
      ? 1
      : Math.min(1, tween.elapsed + Math.min(delta, 0.05) / 0.7);
    const t = tween.elapsed;
    const eased = t * t * (3 - 2 * t);
    camera.quaternion.slerpQuaternions(
      tween.fromQuaternion,
      tween.toQuaternion,
      eased
    );
    const distance =
      tween.fromDistance + (tween.toDistance - tween.fromDistance) * eased;
    camera.position.set(0, 0, distance).applyQuaternion(camera.quaternion);
    camera.setViewOffset(
      size.width,
      size.height,
      tween.fromOffsetX + (tween.toOffsetX - tween.fromOffsetX) * eased,
      tween.fromOffsetY + (tween.toOffsetY - tween.fromOffsetY) * eased,
      size.width,
      size.height
    );
    if (t === 1) {
      transition.current = null;
      controls.current?.update();
      onCameraSettled();
    }
  });
  const enabled = mode === 'desktop' || exploring;
  const latitude = aircraft?.latitude,
    longitude = aircraft?.longitude;
  useEffect(() => {
    if (
      !(camera instanceof PerspectiveCamera) ||
      !size.width ||
      !size.height ||
      !safeRect.width ||
      !safeRect.height
    )
      return;
    const previous = fitted.current;
    const scaleProjection = () => {
      const view = camera.view;
      if (view?.enabled)
        camera.setViewOffset(
          size.width,
          size.height,
          (view.offsetX / view.fullWidth) * size.width,
          (view.offsetY / view.fullHeight) * size.height,
          size.width,
          size.height
        );
    };
    if (intent === 'manual' || (intent === 'follow' && !followAvailable)) {
      transition.current = null;
      scaleProjection();
      return;
    }
    if (!initialReady && intent === 'automatic') return;
    const meaningful =
      !previous ||
      previous.intent !== intent ||
      previous.resetRevision !== resetRevision ||
      previous.mode !== mode ||
      Math.abs(previous.width - size.width) >= 48 ||
      Math.abs(previous.height - size.height) >= 48 ||
      Math.abs(previous.safeRect.width - safeRect.width) >= 48 ||
      Math.abs(previous.safeRect.height - safeRect.height) >= 48;
    if (intent === 'automatic' && !meaningful) {
      scaleProjection();
      return;
    }
    const coordinate =
      latitude !== undefined && longitude !== undefined
        ? { latitude, longitude }
        : null;
    const direction =
      intent === 'follow' && followAvailable && coordinate
        ? new Vector3(
            ...globePosition(coordinate.latitude, coordinate.longitude, 1)
          )
        : overviewInitialDirection(
            route,
            followAvailable ? coordinate : null,
            camera.position
          );
    const frame = overviewCameraFrame({
      width: size.width,
      height: size.height,
      fov: camera.fov,
      safeRect,
      route: intent === 'automatic' ? route : undefined,
      direction,
    });
    const target = camera.clone();
    target.position.copy(direction.multiplyScalar(frame.distance));
    target.lookAt(0, 0, 0);
    controls.current?.target.set(0, 0, 0);
    if (reducedMotion) {
      transition.current = null;
      camera.position.copy(target.position);
      camera.quaternion.copy(target.quaternion);
      camera.setViewOffset(
        size.width,
        size.height,
        frame.offsetX,
        frame.offsetY,
        size.width,
        size.height
      );
      controls.current?.update();
    } else {
      const view = camera.view;
      transition.current = {
        elapsed: 0,
        fromQuaternion: camera.quaternion.clone(),
        toQuaternion: target.quaternion.clone(),
        fromDistance: camera.position.length(),
        toDistance: frame.distance,
        fromOffsetX: view?.enabled
          ? (view.offsetX / view.fullWidth) * size.width
          : 0,
        fromOffsetY: view?.enabled
          ? (view.offsetY / view.fullHeight) * size.height
          : 0,
        toOffsetX: frame.offsetX,
        toOffsetY: frame.offsetY,
      };
    }
    fitted.current = {
      mode,
      width: size.width,
      height: size.height,
      safeRect,
      intent,
      resetRevision,
    };
  }, [
    camera,
    size.width,
    size.height,
    safeRect,
    mode,
    intent,
    followAvailable,
    latitude,
    longitude,
    route,
    reducedMotion,
    initialReady,
    resetRevision,
  ]);
  useEffect(() => {
    const canvas = gl.domElement;
    const orbit = controls.current;
    const pointers = new Map<number, string>();
    const down = (event: PointerEvent) => {
      if (enabled) pointers.set(event.pointerId, event.pointerType);
    };
    const up = (event: PointerEvent) => pointers.delete(event.pointerId);
    canvas.addEventListener('pointerdown', down, true);
    window.addEventListener('pointerup', up);
    window.addEventListener('pointercancel', up);
    return () => {
      for (const [pointerId, pointerType] of pointers) {
        canvas.ownerDocument.dispatchEvent(
          new PointerEvent('pointerup', {
            pointerId,
            pointerType,
            bubbles: true,
          })
        );
        if (canvas.hasPointerCapture(pointerId))
          canvas.releasePointerCapture(pointerId);
      }
      pointers.clear();
      canvas.removeEventListener('pointerdown', down, true);
      window.removeEventListener('pointerup', up);
      window.removeEventListener('pointercancel', up);
      if (orbit) {
        const position = camera.position.clone(),
          quaternion = camera.quaternion.clone();
        orbit.enableDamping = false;
        orbit.update();
        camera.position.copy(position);
        camera.quaternion.copy(quaternion);
        orbit.enableDamping = !reducedMotion;
      }
    };
  }, [enabled, gl, camera, size.width, size.height, reducedMotion]);
  useEffect(() => () => clearTimeout(settleTimer.current), []);
  return (
    <OrbitControls
      ref={controls}
      makeDefault
      enabled={enabled}
      enablePan={false}
      enableDamping={!reducedMotion}
      dampingFactor={0.05}
      minDistance={3}
      maxDistance={28}
      onStart={() => {
        transition.current = null;
        onManual();
      }}
      onChange={() => {
        clearTimeout(settleTimer.current);
        settleTimer.current = setTimeout(onCameraSettled, 200);
      }}
    />
  );
}
