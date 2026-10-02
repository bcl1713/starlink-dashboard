import { useCallback, useEffect, useRef } from 'react';
import { useThree } from '@react-three/fiber';
import { CameraControls, CameraControlsImpl } from '@react-three/drei';
import { PerspectiveCamera, Vector3 } from 'three';
import { OverviewCameraControls } from './overview-camera-controls';
import { globePosition } from './globe-coordinates';
import { useDocumentFullscreen } from '@/hooks/useDocumentFullscreen';
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
  const canvas = useThree((state) => state.gl.domElement);
  const fullscreen = useDocumentFullscreen();
  const centerGlobe = fullscreen && mode === 'desktop';
  const controls = useRef<OverviewCameraControls>(null);
  const fitted = useRef<{
    mode: OverviewLayoutMode;
    width: number;
    height: number;
    safeRect: OverviewSafeRect;
    intent: OverviewCameraIntent;
    resetRevision: number;
    routeFramed: boolean;
    centerGlobe: boolean;
    latitude?: number;
    longitude?: number;
    followAvailable: boolean;
    reducedMotion: boolean;
  } | null>(null);
  const manualFromInput = useRef(false);
  const freezePose = useCallback(() => {
    const control = controls.current;
    if (!control) return;
    // stop() alone snaps to the destination. First make the current pose the target.
    void control.setLookAt(...camera.position.toArray(), 0, 0, 0, false);
    control.stop();
    control.update(0);
  }, [camera]);
  useEffect(() => {
    const pause = () => controls.current?.discardNextDelta();
    document.addEventListener('visibilitychange', pause);
    return () => document.removeEventListener('visibilitychange', pause);
  }, []);
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
      if (!manualFromInput.current) freezePose();
      manualFromInput.current = false;
      fitted.current = null;
      scaleProjection();
      return;
    }
    if (!initialReady && intent === 'automatic') return;
    const meaningful =
      !previous ||
      previous.intent !== intent ||
      previous.reducedMotion !== reducedMotion ||
      previous.resetRevision !== resetRevision ||
      previous.mode !== mode ||
      previous.centerGlobe !== centerGlobe ||
      (!previous.routeFramed && route.length > 0) ||
      Math.abs(previous.width - size.width) >= 48 ||
      Math.abs(previous.height - size.height) >= 48 ||
      Math.abs(previous.safeRect.width - safeRect.width) >= 48 ||
      Math.abs(previous.safeRect.height - safeRect.height) >= 48;
    if (
      !meaningful &&
      (intent === 'automatic' ||
        (previous?.latitude === latitude &&
          previous?.longitude === longitude &&
          previous?.followAvailable === followAvailable &&
          previous?.reducedMotion === reducedMotion))
    ) {
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
      centerGlobe,
    });
    const position = (frame.direction ?? direction)
      .clone()
      .multiplyScalar(frame.distance);
    camera.setViewOffset(
      size.width,
      size.height,
      frame.offsetX,
      frame.offsetY,
      size.width,
      size.height
    );
    const control = controls.current;
    if (control) {
      // Normalize then choose the nearest azimuth, including across the dateline.
      control.normalizeRotations();
      const theta = Math.atan2(position.x, position.z);
      const nearestTheta =
        control.azimuthAngle +
        Math.atan2(
          Math.sin(theta - control.azimuthAngle),
          Math.cos(theta - control.azimuthAngle)
        );
      void control.rotateTo(
        nearestTheta,
        Math.acos(position.y / frame.distance),
        !reducedMotion
      );
      void control.dollyTo(frame.distance, !reducedMotion);
      if (reducedMotion) {
        control.stop();
        control.update(0);
        onCameraSettled();
      }
    }
    fitted.current = {
      mode,
      width: size.width,
      height: size.height,
      safeRect,
      intent,
      resetRevision,
      routeFramed: route.length > 0,
      centerGlobe,
      latitude,
      longitude,
      followAvailable,
      reducedMotion,
    };
  }, [
    camera,
    size.width,
    size.height,
    safeRect,
    mode,
    centerGlobe,
    intent,
    followAvailable,
    latitude,
    longitude,
    route,
    reducedMotion,
    initialReady,
    resetRevision,
    onCameraSettled,
    freezePose,
    enabled,
  ]);
  useEffect(() => {
    const wheel = (event: WheelEvent) => {
      if (!enabled) return;
      if (event.ctrlKey || event.metaKey) {
        // Keep native browser zoom available before CameraControls consumes the wheel.
        event.stopImmediatePropagation();
        return;
      }
      if (event.deltaY && intent !== 'manual') freezePose();
    };
    // Rebase before CameraControls adds its wheel delta to the pending dolly target.
    canvas.addEventListener('wheel', wheel, { capture: true, passive: true });
    return () => canvas.removeEventListener('wheel', wheel, true);
  }, [canvas, enabled, intent, freezePose]);
  useEffect(() => {
    const control = controls.current;
    return () => {
      // camera-controls owns pointer listeners and cancels active drags.
      control?.cancel();
    };
  }, [enabled, size.width, size.height]);
  const { ACTION } = CameraControlsImpl;
  return (
    <CameraControls
      ref={controls}
      impl={OverviewCameraControls}
      makeDefault
      enabled={enabled}
      smoothTime={reducedMotion ? 0 : 0.4}
      draggingSmoothTime={reducedMotion ? 0 : 0.1}
      maxSpeed={reducedMotion ? Infinity : 3}
      minDistance={3}
      maxDistance={28}
      mouseButtons={{
        left: ACTION.ROTATE,
        middle: ACTION.DOLLY,
        right: ACTION.ROTATE,
        wheel: ACTION.DOLLY,
      }}
      touches={{
        one: ACTION.TOUCH_ROTATE,
        two: ACTION.TOUCH_DOLLY_ROTATE,
        three: ACTION.TOUCH_ROTATE,
      }}
      onControlStart={() => {
        freezePose();
        manualFromInput.current = intent !== 'manual';
        onManual();
      }}
      onControl={() => {
        if (intent !== 'manual') {
          const control = controls.current;
          if (control)
            void control.rotateTo(
              control.azimuthAngle,
              control.polarAngle,
              false
            );
        }
        if (intent !== 'manual') manualFromInput.current = true;
        onManual();
      }}
      onSleep={onCameraSettled}
    />
  );
}
