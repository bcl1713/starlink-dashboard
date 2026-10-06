import { useRef, type RefObject } from 'react';
import { useFrame } from '@react-three/fiber';
import { Matrix4, Vector2, type Object3D } from 'three';
import type { WeatherCapabilities } from '@/services/overview-weather';
import {
  DetailDemandStabilizer,
  selectDetail,
  type DetailDemand,
} from './weather-detail-selection';

export function OverviewWeatherCameraObserver({
  capabilities,
  globe,
  onDemand,
}: {
  capabilities: WeatherCapabilities | null;
  globe?: RefObject<Object3D | null>;
  onDemand(demand: DetailDemand): void;
}) {
  const state = useRef({
    next: 0,
    capabilities,
    stabilizer: new DetailDemandStabilizer(),
    previous: null as DetailDemand | null,
    buffer: new Vector2(),
  });
  useFrame(({ camera, gl }) => {
    const owned = state.current;
    if (!capabilities) {
      owned.previous = null;
      owned.stabilizer = new DetailDemandStabilizer();
      owned.capabilities = null;
      return;
    }
    if (owned.capabilities !== capabilities) {
      owned.capabilities = capabilities;
      owned.stabilizer = new DetailDemandStabilizer();
      owned.previous = null;
    }
    const now = performance.now();
    if (now < owned.next) return;
    owned.next = now + 250;
    camera.updateMatrixWorld();
    globe?.current?.updateWorldMatrix(true, false);
    gl.getDrawingBufferSize(owned.buffer);
    const demand = selectDetail(
      {
        projection: camera.projectionMatrix.toArray(),
        cameraWorld: camera.matrixWorld.toArray(),
        globeWorld: (globe?.current?.matrixWorld ?? new Matrix4()).toArray(),
        drawingBuffer: [owned.buffer.x, owned.buffer.y],
      },
      capabilities,
      owned.previous
    );
    owned.previous = demand;
    const stable = owned.stabilizer.update(demand, now);
    if (stable) onDemand(stable);
  });
  return null;
}
