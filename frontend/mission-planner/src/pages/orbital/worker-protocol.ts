import { CatalogPropagator } from './propagation';
import {
  MAX_OBJECTS,
  type CatalogEnvelope,
  type OrbitalEndpoints,
  type OrbitalSnapshot,
} from './types';

export type WorkerInput =
  | { type: 'start'; generation: number; catalog: CatalogEnvelope }
  | { type: 'endpoints'; generation: number; endpoints: OrbitalEndpoints }
  | { type: 'recycle'; generation: number; snapshot: OrbitalSnapshot };
export type WorkerOutput =
  | { type: 'snapshot'; generation: number; snapshot: OrbitalSnapshot }
  | { type: 'error'; generation: number; message: string };
type Bank = {
  positions: Float64Array<ArrayBuffer>;
  valid: Uint8Array<ArrayBuffer>;
  available: boolean;
};

export function transfers(snapshot: OrbitalSnapshot): ArrayBuffer[] {
  return [snapshot.positionsKm.buffer, snapshot.valid.buffer];
}

/** Three fixed-capacity banks survive catalog changes; exhausted banks drop ticks. */
export class OrbitalWorkerRuntime {
  private banks: Bank[] = [];
  private timer: ReturnType<typeof setInterval> | undefined;
  private catalog: CatalogEnvelope | undefined;
  private propagator: CatalogPropagator | undefined;
  private generation = 0;
  private disposed = false;
  private send: (message: WorkerOutput, transfer: ArrayBuffer[]) => void;
  private clock: () => number;
  endpoints: OrbitalEndpoints = { aircraft: null, pop: null };
  constructor(
    send: (message: WorkerOutput, transfer: ArrayBuffer[]) => void,
    clock = Date.now
  ) {
    this.send = send;
    this.clock = clock;
  }
  get allocatedBanks() {
    return this.banks.length;
  }
  receive(message: WorkerInput) {
    if (this.disposed) return;
    if (message.type === 'start') {
      this.generation = message.generation;
      this.catalog = message.catalog;
      this.propagator = new CatalogPropagator(message.catalog.objects);
      if (!this.banks.length)
        this.banks = Array.from({ length: 3 }, () => ({
          positions: new Float64Array(MAX_OBJECTS * 3),
          valid: new Uint8Array(MAX_OBJECTS),
          available: true,
        }));
      if (!this.timer) this.timer = setInterval(() => this.tick(), 1000);
      this.tick();
      return;
    }
    if (message.generation !== this.generation) return;
    if (message.type === 'endpoints') this.endpoints = message.endpoints;
    if (message.type === 'recycle') {
      const bank = this.banks[message.snapshot.bankId];
      if (
        !bank ||
        bank.available ||
        message.snapshot.positionsKm.buffer.byteLength !==
          MAX_OBJECTS * 3 * 8 ||
        message.snapshot.valid.buffer.byteLength !== MAX_OBJECTS
      )
        return;
      bank.positions = new Float64Array(message.snapshot.positionsKm.buffer);
      bank.valid = new Uint8Array(message.snapshot.valid.buffer);
      bank.available = true;
    }
  }
  private tick() {
    if (!this.propagator || !this.catalog || this.disposed) return;
    const bankId = this.banks.findIndex((bank) => bank.available);
    if (bankId < 0) return;
    const bank = this.banks[bankId],
      started = performance.now();
    try {
      const result = this.propagator.update(
        this.clock(),
        bank.positions,
        bank.valid
      );
      const snapshot: OrbitalSnapshot = {
        ...result,
        generation: this.generation,
        catalogGeneration: this.catalog.generation,
        bankId,
        route: null,
        updateMs: performance.now() - started,
      };
      bank.available = false;
      this.send(
        { type: 'snapshot', generation: this.generation, snapshot },
        transfers(snapshot)
      );
    } catch (error) {
      this.send(
        { type: 'error', generation: this.generation, message: String(error) },
        []
      );
      this.dispose();
    }
  }
  dispose() {
    this.disposed = true;
    clearInterval(this.timer);
    this.timer = undefined;
    this.banks = [];
    this.propagator = undefined;
    this.catalog = undefined;
  }
}
