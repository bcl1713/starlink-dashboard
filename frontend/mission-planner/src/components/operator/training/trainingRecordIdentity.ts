import type { SavedRecord } from '@/types/operator';

/** API JSON object member order is not part of record identity. */
export function sameJson(left: unknown, right: unknown): boolean {
  if (left === right) return true;
  if (Array.isArray(left) || Array.isArray(right))
    return (
      Array.isArray(left) &&
      Array.isArray(right) &&
      left.length === right.length &&
      left.every((value, index) => sameJson(value, right[index]))
    );
  if (!left || !right || typeof left !== 'object' || typeof right !== 'object')
    return false;
  const a = left as Record<string, unknown>,
    b = right as Record<string, unknown>;
  const keys = Object.keys(a);
  return (
    keys.length === Object.keys(b).length &&
    keys.every(
      (key) =>
        Object.prototype.hasOwnProperty.call(b, key) && sameJson(a[key], b[key])
    )
  );
}
export function sameRecord(left: SavedRecord, right: SavedRecord): boolean {
  return (
    left.record_id === right.record_id &&
    left.version === right.version &&
    left.command_id === right.command_id &&
    left.mission_id === right.mission_id &&
    sameJson(left, right)
  );
}
