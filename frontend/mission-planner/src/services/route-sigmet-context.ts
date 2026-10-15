import { sha256 } from '@noble/hashes/sha2.js';
import { bytesToHex } from '@noble/hashes/utils.js';

/** Byte identity shared with the backend; coordinates are ordered lon/lat. */
export function routeContextKey(
  source: 'ordinary' | 'simulation',
  routeId: string,
  runtimeId: string | null,
  runId: string | null,
  points: readonly (readonly number[])[]
): string {
  if (
    !['ordinary', 'simulation'].includes(source) ||
    !routeId ||
    [...routeId].length > 256 ||
    (source === 'simulation'
      ? !runtimeId || !runId
      : runtimeId !== null || runId !== null) ||
    [runtimeId, runId].some((id) => id !== null && [...id].length > 256) ||
    !Array.isArray(points) ||
    points.length > 20_000
  )
    throw new Error('Invalid route context');
  for (const point of points) {
    if (
      point.length !== 2 ||
      !point.every(
        (value: number) => typeof value === 'number' && Number.isFinite(value)
      ) ||
      Math.abs(point[0]) > 180 ||
      Math.abs(point[1]) > 90
    )
      throw new Error('Invalid route coordinates');
  }
  const encoder = new TextEncoder();
  const prefix = encoder.encode('route-context-v1\0');
  const fields = [source, routeId, runtimeId ?? '', runId ?? ''].map((value) =>
    encoder.encode(value)
  );
  const bytes = new Uint8Array(
    prefix.length +
      fields.reduce((size, field) => size + 4 + field.length, 0) +
      4 +
      points.length * 16
  );
  const view = new DataView(bytes.buffer);
  bytes.set(prefix);
  let offset = prefix.length;
  for (const field of fields) {
    view.setUint32(offset, field.length);
    offset += 4;
    bytes.set(field, offset);
    offset += field.length;
  }
  view.setUint32(offset, points.length);
  offset += 4;
  for (const point of points) {
    view.setFloat64(offset, point[0] || 0);
    view.setFloat64(offset + 8, point[1] || 0);
    offset += 16;
  }
  return bytesToHex(sha256(bytes));
}
