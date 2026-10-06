// @vitest-environment jsdom
import { create, act } from '@react-three/test-renderer';
import { expect, it, vi } from 'vitest';
import * as THREE from 'three';
import { AviationLayer } from './AviationLayer';
import { createAviationDrawing } from './aviation-renderer';
import { emptyAviationView, type AviationView } from './aviation-controller';
import { parseAviationFeatures } from '@/services/aviation-features';
import { collection, NOW, station } from './fixtures';

it('selects a tapped station, suppresses globe drags and releases highlight resources separately from base geometry', async () => {
  const data = parseAviationFeatures(collection([station()]), 'metar');
  const drawing = createAviationDrawing(data, 'metar', NOW);
  const view: AviationView = {
    ...emptyAviationView,
    now: NOW,
    layers: {
      ...emptyAviationView.layers,
      metar: { state: 'current', data, drawing },
    },
  };
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
  camera.position.set(5, 0, 0);
  camera.lookAt(0, 0, 0);
  camera.updateMatrixWorld();
  const selected = vi.fn();
  let canvas: HTMLCanvasElement;
  const renderer = await create(
    <AviationLayer
      view={view}
      selection={{ layer: 'metar', id: 'test-station' }}
      onSelect={selected}
    />,
    {
      camera,
      width: 1000,
      height: 1000,
      beforeReturn: (c) => {
        canvas = c;
        c.getBoundingClientRect = () => new DOMRect(0, 0, 1000, 1000);
      },
    }
  );
  const pointer = (
    target: EventTarget,
    type: string,
    x: number,
    y = 500,
    primary = true
  ) => {
    const event = new MouseEvent(type, { clientX: x, clientY: y, button: 0 });
    Object.defineProperties(event, {
      pointerId: { value: primary ? 1 : 2 },
      isPrimary: { value: primary },
    });
    target.dispatchEvent(event);
  };
  try {
    await act(async () => {
      pointer(canvas!, 'pointerdown', 500);
      pointer(canvas!, 'pointerup', 500);
    });
    expect(selected).toHaveBeenLastCalledWith([
      { layer: 'metar', id: 'test-station' },
    ]);
    selected.mockClear();
    await act(async () => {
      pointer(canvas!, 'pointerdown', 500);
      pointer(window, 'pointermove', 520);
      pointer(canvas!, 'pointerup', 500);
    });
    expect(selected).not.toHaveBeenCalled();
    await act(async () => {
      pointer(canvas!, 'pointerdown', 500);
      pointer(canvas!, 'pointerdown', 550, 500, false);
      pointer(canvas!, 'pointerup', 500);
    });
    expect(selected).not.toHaveBeenCalled();
    const highlight = renderer.scene.instance.getObjectByName(
      'Selected aviation weather report'
    ) as THREE.Points;
    expect(highlight).toBeDefined();
    expect(
      (highlight.material as THREE.PointsMaterial).color.getHexString()
    ).toBe('ffffff');
    const geometryDisposed = vi.fn(),
      materialDisposed = vi.fn(),
      baseDisposed = vi.fn();
    highlight.geometry.addEventListener('dispose', geometryDisposed);
    (highlight.material as THREE.Material).addEventListener(
      'dispose',
      materialDisposed
    );
    (drawing.object as THREE.Points).geometry.addEventListener(
      'dispose',
      baseDisposed
    );
    await renderer.update(
      <AviationLayer view={view} selection={null} onSelect={selected} />
    );
    expect(
      renderer.scene.instance.getObjectByName(
        'Selected aviation weather report'
      )
    ).toBeUndefined();
    expect(geometryDisposed).toHaveBeenCalledOnce();
    expect(materialDisposed).toHaveBeenCalledOnce();
    expect(baseDisposed).not.toHaveBeenCalled();
  } finally {
    await renderer.unmount();
    drawing.dispose();
  }
});
