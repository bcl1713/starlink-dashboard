import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type RefObject,
} from 'react';
import { useFrame, useThree, type ThreeEvent } from '@react-three/fiber';
import { OverviewMapLabel } from '../OverviewMapLabel';
import * as THREE from 'three';
import {
  createStarMarkerChevronResources,
  updateStarMarkerChevronStyle,
} from '../overview-star-marker-rendering';
import { globePosition } from '../globe-coordinates';
import {
  ADSB_MARKER_RADIUS,
  adsbClickAllowed,
  buildAdsbMarkerInstances,
  createAdsbEarthOccluder,
  isAdsbMarkerVisible,
  resizeAdsbMarkerMeshes,
  type AdsbMarkerBatch,
  type AdsbPointerGesture,
} from './overview-adsb-marker-rendering';
import type { AdsbContactView } from './overview-adsb-state';
import './OverviewAdsb.css';
import {
  DEFAULT_CHEVRON_SETTINGS,
  type ChevronSettings,
} from '../overview-chevron-settings';

function visualKey(contacts: readonly AdsbContactView[]): string {
  return contacts
    .map(
      (c) =>
        `${c.hex}:${c.latitude}:${c.longitude}:${c.track_degrees}:${c.freshness}`
    )
    .join('|');
}
export function OverviewAdsbLayer({
  contacts,
  globeOccluder,
  onSelect,
  onVisibleHexesChange,
  chevronSettings = DEFAULT_CHEVRON_SETTINGS,
}: {
  contacts: readonly AdsbContactView[];
  chevronSettings?: Readonly<ChevronSettings>;
  globeOccluder: RefObject<THREE.Group>;
  onSelect: (hex: string) => void;
  onVisibleHexesChange: (hexes: readonly string[]) => void;
}) {
  const { camera, gl, size } = useThree();
  const key = visualKey(contacts);
  const [visual, setVisual] = useState(() => ({ key, contacts }));
  if (visual.key !== key) setVisual({ key, contacts });
  const instances = useMemo(
    () => buildAdsbMarkerInstances(visual.contacts),
    [visual.contacts]
  );
  const { current: currentBatch, stale: staleBatch } = instances;
  const group = useMemo(() => new THREE.Group(), []);
  const earthOccluder = useMemo(
    () => ({ current: createAdsbEarthOccluder(globeOccluder) }),
    [globeOccluder]
  );
  const gesture = useRef<AdsbPointerGesture | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const visible = useRef<readonly string[]>([]);
  const lastPose = useRef('');
  const markerResources = useRef<
    ReturnType<typeof createStarMarkerChevronResources>[]
  >([]);
  useLayoutEffect(() => {
    const resources = (
      [
        ['current', instances.current],
        ['stale', instances.stale],
      ] as const
    ).map(([kind, batch]) => {
      const chevron = createStarMarkerChevronResources({
        color: kind === 'stale' ? '#b99554' : '#efb85b',
        glowIntensity: 0.65,
        stale: kind === 'stale',
      });
      const { geometry, material, haloGeometry, haloMaterial } = chevron;
      const mesh = new THREE.InstancedMesh(
        geometry,
        material,
        batch.hexes.length
      );
      mesh.instanceMatrix.array.set(batch.matrices);
      mesh.instanceMatrix.needsUpdate = true;
      mesh.userData.adsbBatch = batch;
      mesh.renderOrder = 10;
      const halo = new THREE.InstancedMesh(
        haloGeometry,
        haloMaterial,
        batch.hexes.length
      );
      halo.instanceMatrix = mesh.instanceMatrix;
      halo.userData.adsbHaloBatch = batch;
      halo.renderOrder = 9;
      halo.frustumCulled = false;
      halo.raycast = () => {};
      mesh.computeBoundingSphere();
      group.add(mesh, halo);
      return { mesh, halo, chevron };
    });
    markerResources.current = resources.map((r) => r.chevron);
    return () => {
      markerResources.current = [];
      for (const r of resources) {
        group.remove(r.mesh, r.halo);
        r.mesh.dispose();
        r.halo.dispose();
        r.chevron.geometry.dispose();
        r.chevron.material.dispose();
        r.chevron.haloGeometry.dispose();
        r.chevron.haloMaterial.dispose();
      }
    };
  }, [group, instances]);
  useLayoutEffect(() => {
    for (const resources of markerResources.current)
      updateStarMarkerChevronStyle(
        resources,
        chevronSettings,
        chevronSettings.trafficSizePixels
      );
  }, [instances, chevronSettings]);
  const markerMatrix = useMemo(() => new THREE.Matrix4(), []);
  const resizeMarkers = useCallback(() => {
    resizeAdsbMarkerMeshes(
      group,
      camera,
      size.height,
      markerMatrix,
      chevronSettings.trafficSizePixels
    );
  }, [
    camera,
    group,
    markerMatrix,
    size.height,
    chevronSettings.trafficSizePixels,
  ]);
  useLayoutEffect(() => {
    resizeMarkers();
  }, [instances, resizeMarkers]);
  useEffect(() => {
    const canvas = gl.domElement;
    const down = (event: PointerEvent) => {
      gesture.current = {
        x: event.clientX,
        y: event.clientY,
        maxDistance: 0,
        cancelled: false,
      };
    };
    const move = (event: PointerEvent) => {
      const start = gesture.current;
      if (start)
        start.maxDistance = Math.max(
          start.maxDistance,
          Math.hypot(event.clientX - start.x, event.clientY - start.y)
        );
    };
    const cancel = () => {
      if (gesture.current) gesture.current.cancelled = true;
    };
    canvas.addEventListener('pointerdown', down);
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', move);
    window.addEventListener('pointercancel', cancel);
    return () => {
      canvas.removeEventListener('pointerdown', down);
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', move);
      window.removeEventListener('pointercancel', cancel);
      gesture.current = null;
    };
  }, [gl]);
  const measure = useCallback(() => {
    const hexes = [currentBatch, staleBatch]
      .flatMap((batch) =>
        batch.hexes.filter((_, i) =>
          isAdsbMarkerVisible(batch.positions[i], camera)
        )
      )
      .sort();
    if (visible.current.join('|') !== hexes.join('|')) {
      visible.current = hexes;
      onVisibleHexesChange(hexes);
    }
  }, [camera, currentBatch, staleBatch, onVisibleHexesChange]);
  const schedule = useCallback(() => {
    if (timer.current !== null) return;
    timer.current = setTimeout(() => {
      timer.current = null;
      measure();
    }, 75);
  }, [measure]);
  useEffect(() => {
    schedule();
    return () => {
      if (timer.current !== null) clearTimeout(timer.current);
      timer.current = null;
    };
  }, [schedule, size.width, size.height, contacts]);
  useFrame(() => {
    const pose = `${camera.position.toArray()}|${camera.quaternion.toArray()}|${camera.projectionMatrix.elements}|${size.height}`;
    if (pose !== lastPose.current) {
      lastPose.current = pose;
      resizeMarkers();
      schedule();
    }
  });
  const click = (event: ThreeEvent<MouseEvent>) => {
    const batch = event.object.userData.adsbBatch as
        | AdsbMarkerBatch
        | undefined,
      i = event.instanceId;
    if (
      !batch ||
      i === undefined ||
      !gesture.current ||
      !adsbClickAllowed(gesture.current, event.nativeEvent) ||
      !isAdsbMarkerVisible(batch.positions[i], camera)
    )
      return;
    event.stopPropagation();
    onSelect(batch.hexes[i]);
  };
  return (
    <>
      <primitive object={group} dispose={null} onClick={click} />
      {contacts
        .filter((c) => c.included)
        .map((c) => (
          <OverviewMapLabel
            key={c.hex}
            id={`adsb:${c.hex}`}
            kind="adsb"
            hex={c.hex}
            text={`${c.label}${c.freshness === 'stale' ? ' · ◷ Stale' : ''}`}
            title={`${c.label} · ${c.hex}`}
            position={globePosition(
              c.latitude,
              c.longitude,
              ADSB_MARKER_RADIUS
            )}
            globeOccluder={earthOccluder}
          />
        ))}
    </>
  );
}
