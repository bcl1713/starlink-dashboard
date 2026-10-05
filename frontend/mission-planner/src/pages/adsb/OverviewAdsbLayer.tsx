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
import { Html } from '@react-three/drei';
import * as THREE from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { globePosition } from '../globe-coordinates';
import {
  ADSB_MARKER_RADIUS,
  adsbClickAllowed,
  buildAdsbMarkerInstances,
  createAdsbEarthOccluder,
  isAdsbMarkerVisible,
  type AdsbMarkerBatch,
  type AdsbPointerGesture,
} from './overview-adsb-marker-rendering';
import { layoutAdsbLabels, type Bounds } from './overview-adsb-label-layout';
import type { AdsbContactView } from './overview-adsb-state';
import './OverviewAdsb.css';

function aircraftGeometry(stale: boolean): THREE.BufferGeometry {
  const shape = new THREE.Shape();
  shape.moveTo(0, 1);
  shape.lineTo(0.16, 0.2);
  shape.lineTo(0.8, -0.2);
  shape.lineTo(0.8, -0.4);
  shape.lineTo(0.16, -0.2);
  shape.lineTo(0.16, -0.7);
  shape.lineTo(0.4, -0.85);
  shape.lineTo(0.4, -1);
  shape.lineTo(0, -0.85);
  shape.lineTo(-0.4, -1);
  shape.lineTo(-0.4, -0.85);
  shape.lineTo(-0.16, -0.7);
  shape.lineTo(-0.16, -0.2);
  shape.lineTo(-0.8, -0.4);
  shape.lineTo(-0.8, -0.2);
  shape.lineTo(-0.16, 0.2);
  shape.closePath();
  const glyph = new THREE.ShapeGeometry(shape);
  if (!stale) return glyph;
  const ring = new THREE.RingGeometry(1.2, 1.32, 8);
  const combined = mergeGeometries([glyph, ring]);
  glyph.dispose();
  ring.dispose();
  return combined;
}
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
}: {
  contacts: readonly AdsbContactView[];
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
  const previousOffsets = useRef<Record<string, readonly [number, number]>>({});
  const [offsets, setOffsets] = useState<
    Record<string, readonly [number, number]>
  >({});
  const [visible, setVisible] = useState<readonly string[]>([]);
  const lastPose = useRef('');
  useLayoutEffect(() => {
    const resources = (
      [
        ['current', instances.current],
        ['stale', instances.stale],
      ] as const
    ).map(([kind, batch]) => {
      const geometry = aircraftGeometry(kind === 'stale');
      const material = new THREE.MeshBasicMaterial({
        color: kind === 'stale' ? '#a89b78' : '#78aabb',
        side: THREE.DoubleSide,
        depthTest: true,
        depthWrite: true,
      });
      const mesh = new THREE.InstancedMesh(
        geometry,
        material,
        batch.hexes.length
      );
      mesh.instanceMatrix.array.set(batch.matrices);
      mesh.instanceMatrix.needsUpdate = true;
      mesh.userData.adsbBatch = batch;
      mesh.computeBoundingSphere();
      group.add(mesh);
      return { mesh, geometry, material };
    });
    return () => {
      for (const r of resources) {
        group.remove(r.mesh);
        r.mesh.dispose();
        r.geometry.dispose();
        r.material.dispose();
      }
    };
  }, [group, instances]);
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
    setVisible((old) => (old.join('|') === hexes.join('|') ? old : hexes));
    onVisibleHexesChange(hexes);
    const stage = gl.domElement.closest<HTMLElement>('.overview-map-stage');
    if (!stage) return;
    const origin = stage.getBoundingClientRect();
    const bounds = (node: HTMLElement): Bounds => {
      const b = node.getBoundingClientRect();
      return {
        x: b.x - origin.x,
        y: b.y - origin.y,
        width: b.width,
        height: b.height,
      };
    };
    const visibleSet = new Set(hexes);
    const labels = [...stage.querySelectorAll<HTMLElement>('[data-adsb-label]')]
      .filter((node) => visibleSet.has(node.dataset.adsbLabel!))
      .map((node) => {
        const id = node.dataset.adsbLabel!,
          b = bounds(node),
          old = previousOffsets.current[id] ?? [0, 0];
        return { id, bounds: { ...b, x: b.x - old[0], y: b.y - old[1] } };
      });
    const reserved = [
      ...stage.querySelectorAll<HTMLElement>(
        '.overview-planned-satellite,.overview-arrival,.globe-legend,.overview-fullscreen-control,.overview-map-status,.overview-map-controls,[data-poi-label]'
      ),
    ]
      .filter(
        (node) =>
          node.getBoundingClientRect().width > 0 &&
          getComputedStyle(node).display !== 'none'
      )
      .map(bounds);
    const next = layoutAdsbLabels(
      labels,
      { width: origin.width, height: origin.height },
      reserved
    );
    previousOffsets.current = next;
    setOffsets((old) =>
      JSON.stringify(old) === JSON.stringify(next) ? old : next
    );
  }, [camera, gl, currentBatch, staleBatch, onVisibleHexesChange]);
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
    const pose = `${camera.position.toArray()}|${camera.quaternion.toArray()}|${camera.projectionMatrix.elements}`;
    if (pose !== lastPose.current) {
      lastPose.current = pose;
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
  const visibleSet = new Set(visible);
  return (
    <>
      <primitive object={group} dispose={null} onClick={click} />
      {contacts
        .filter((c) => c.included)
        .map((c) => (
          <Html
            key={c.hex}
            position={globePosition(
              c.latitude,
              c.longitude,
              ADSB_MARKER_RADIUS
            )}
            occlude={[earthOccluder]}
            zIndexRange={[0, 0]}
            style={{ pointerEvents: 'none' }}
            wrapperClass="adsb-label-wrapper"
          >
            <span
              data-adsb-label={c.hex}
              className={`adsb-map-label${c.freshness === 'stale' ? ' adsb-map-label--stale' : ''}`}
              title={`${c.label} · ${c.hex}`}
              style={{
                visibility: visibleSet.has(c.hex) ? 'visible' : 'hidden',
                transform: `translate(${offsets[c.hex]?.[0] ?? 0}px,${offsets[c.hex]?.[1] ?? 0}px)`,
              }}
            >
              {c.label}
              {c.freshness === 'stale' ? ' · ◷ Stale' : ''}
            </span>
          </Html>
        ))}
    </>
  );
}
