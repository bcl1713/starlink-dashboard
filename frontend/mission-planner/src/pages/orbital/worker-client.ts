import { transfers, type WorkerInput } from './worker-protocol';
import {
  MAX_OBJECTS,
  type CatalogEnvelope,
  type OrbitalEndpoints,
  type OrbitalSnapshot,
} from './types';

export interface WorkerHandle {
  postMessage(message: WorkerInput, transfer?: Transferable[]): void;
  terminate(): void;
  onmessage: ((event: MessageEvent) => void) | null;
  onerror: ((event: ErrorEvent) => void) | null;
}
export function snapshotIsValid(value: unknown): value is OrbitalSnapshot {
  if (!value || typeof value !== 'object') return false;
  const s = value as Partial<OrbitalSnapshot>;
  return (
    Number.isFinite(s.utcMs) &&
    Number.isFinite(s.updateMs) &&
    typeof s.catalogGeneration === 'string' &&
    Number.isInteger(s.generation) &&
    Number.isInteger(s.bankId) &&
    s.bankId! >= 0 &&
    s.bankId! < 3 &&
    Array.isArray(s.ids) &&
    s.ids.length <= MAX_OBJECTS &&
    s.ids.every((id) => typeof id === 'string' && /^[1-9]\d{0,8}$/.test(id)) &&
    new Set(s.ids).size === s.ids.length &&
    s.positionsKm instanceof Float64Array &&
    s.valid instanceof Uint8Array &&
    s.positionsKm.length === s.ids.length * 3 &&
    s.valid.length === s.ids.length &&
    s.positionsKm.every(Number.isFinite) &&
    s.valid.every((v) => v === 0 || v === 1) &&
    (s.route === null ||
      (typeof s.route === 'object' && Array.isArray(s.route?.ids)))
  );
}
export class OrbitalWorkerClient {
  private worker: WorkerHandle;
  private disposed = false;
  private catalogGeneration = '';
  private generation: number;
  private snapshot: (snapshot: OrbitalSnapshot) => void;
  private error: (error: Error) => void;
  constructor(
    generation: number,
    snapshot: (snapshot: OrbitalSnapshot) => void,
    error: (error: Error) => void,
    factory: () => WorkerHandle = () =>
      new Worker(new URL('./orbital.worker.ts', import.meta.url), {
        type: 'module',
      })
  ) {
    this.generation = generation;
    this.snapshot = snapshot;
    this.error = error;
    this.worker = factory();
    this.worker.onmessage = ({ data }) => {
      if (this.disposed || data?.generation !== this.generation) return;
      if (
        data.type !== 'snapshot' ||
        !snapshotIsValid(data.snapshot) ||
        data.snapshot.generation !== this.generation
      ) {
        this.error(new Error('Invalid orbital worker response'));
        return;
      }
      if (data.snapshot.catalogGeneration !== this.catalogGeneration) {
        this.recycle(data.snapshot);
        return;
      }
      this.snapshot(data.snapshot);
    };
    this.worker.onerror = () => {
      if (!this.disposed) this.error(new Error('Orbital worker failed'));
    };
  }
  start(catalog: CatalogEnvelope) {
    if (!this.disposed) {
      this.catalogGeneration = catalog.generation;
      this.worker.postMessage({
        type: 'start',
        generation: this.generation,
        catalog,
      });
    }
  }
  setEndpoints(endpoints: OrbitalEndpoints) {
    if (!this.disposed)
      this.worker.postMessage({
        type: 'endpoints',
        generation: this.generation,
        endpoints,
      });
  }
  recycle(snapshot: OrbitalSnapshot) {
    if (!this.disposed && snapshot.generation === this.generation)
      this.worker.postMessage(
        { type: 'recycle', generation: this.generation, snapshot },
        transfers(snapshot)
      );
  }
  dispose() {
    if (this.disposed) return;
    this.disposed = true;
    this.worker.onmessage = null;
    this.worker.onerror = null;
    this.worker.terminate();
  }
}
