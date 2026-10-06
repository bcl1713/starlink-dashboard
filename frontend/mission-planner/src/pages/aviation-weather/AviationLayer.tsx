import type { AviationView } from './aviation-controller';
import { useEffect, useLayoutEffect, useMemo, useRef } from 'react';
import { useThree } from '@react-three/fiber';
import * as THREE from 'three';
import {
  pickAviationFeatures,
  resolveAviationSelection,
  type AviationSelection,
} from './aviation-inspection';
import { createAviationDrawing } from './aviation-renderer';
// Geometry/material ownership belongs to the controller; React only attaches
// admitted objects. Fiber must not dispose objects retained between renders.
export function AviationLayer({
  view,
  selection,
  onSelect,
}: {
  view: AviationView;
  selection: AviationSelection | null;
  onSelect: (candidates: readonly AviationSelection[]) => void;
}) {
  const { camera, gl } = useThree();
  const gesture = useRef<{
    id: number;
    x: number;
    y: number;
    distance: number;
  } | null>(null);
  const highlight = useMemo(() => new THREE.Group(), []);
  const feature = resolveAviationSelection(view, selection);
  const layer = selection?.layer;
  const base = layer ? view.layers[layer].drawing : undefined;
  useLayoutEffect(() => {
    if (!feature?.geometry || !layer || !base) return;
    const data = view.layers[layer].data!;
    const drawing = createAviationDrawing(
      { ...data, features: [feature] },
      layer,
      view.now
    );
    const total =
      Object.values(view.layers).reduce(
        (sum, item) => sum + (item.drawing?.bytes ?? 0),
        0
      ) + drawing.bytes;
    if (total > 16 * 1024 ** 2) {
      drawing.dispose();
      return;
    }
    drawing.object.name = 'Selected aviation weather report';
    drawing.object.traverse((object) => {
      object.renderOrder = 26;
      const material = (object as THREE.Mesh).material as
        | THREE.MeshBasicMaterial
        | THREE.PointsMaterial
        | THREE.LineBasicMaterial
        | undefined;
      if (material) {
        material.color.set('#ffffff');
        material.vertexColors = false;
        material.opacity = object.type === 'Mesh' ? 0.45 : 1;
        if (material instanceof THREE.PointsMaterial) material.size = 0.026;
        material.needsUpdate = true;
      }
    });
    highlight.add(drawing.object);
    return () => {
      highlight.remove(drawing.object);
      drawing.dispose();
    };
  }, [feature, layer, base, highlight, view]);
  useEffect(() => {
    const canvas = gl.domElement;
    const down = (event: PointerEvent) => {
      if (!event.isPrimary) {
        gesture.current = null;
        return;
      }
      if (event.button !== 0) return;
      gesture.current = {
        id: event.pointerId,
        x: event.clientX,
        y: event.clientY,
        distance: 0,
      };
    };
    const move = (event: PointerEvent) => {
      const start = gesture.current;
      if (start?.id === event.pointerId)
        start.distance = Math.max(
          start.distance,
          Math.hypot(event.clientX - start.x, event.clientY - start.y)
        );
    };
    const up = (event: PointerEvent) => {
      const start = gesture.current;
      move(event);
      gesture.current = null;
      if (!start || start.id !== event.pointerId || start.distance > 5) return;
      const rect = canvas.getBoundingClientRect();
      const candidates = pickAviationFeatures(
        view,
        camera,
        { x: event.clientX - rect.left, y: event.clientY - rect.top },
        rect
      );
      if (candidates.length) onSelect(candidates);
    };
    const cancel = () => {
      gesture.current = null;
    };
    canvas.addEventListener('pointerdown', down);
    window.addEventListener('pointermove', move);
    canvas.addEventListener('pointerup', up);
    window.addEventListener('pointerup', cancel);
    window.addEventListener('pointercancel', cancel);
    return () => {
      canvas.removeEventListener('pointerdown', down);
      window.removeEventListener('pointermove', move);
      canvas.removeEventListener('pointerup', up);
      window.removeEventListener('pointerup', cancel);
      window.removeEventListener('pointercancel', cancel);
    };
  }, [view, camera, gl, onSelect]);
  return (
    <group name="Native aviation weather">
      {Object.entries(view.layers).map(([layer, item]) =>
        item.drawing ? (
          <primitive
            key={`${layer}:${item.drawing.object.uuid}`}
            object={item.drawing.object}
            dispose={null}
          />
        ) : null
      )}
      <primitive object={highlight} dispose={null} />
    </group>
  );
}
