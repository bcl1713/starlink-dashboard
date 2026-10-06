import { gridFixture } from './gfs-grid';
import { parseGridDescriptor, type GridLease } from '@/services/aviation-grid';
export function lease(): GridLease {
  const f = gridFixture();
  return {
    descriptor: parseGridDescriptor(f.descriptor),
    u: new Int16Array(f.buffers.u.buffer),
    v: new Int16Array(f.buffers.v.buffer),
    t: new Int16Array(f.buffers.t.buffer),
    mask: f.buffers.mask,
    release() {},
  };
}
