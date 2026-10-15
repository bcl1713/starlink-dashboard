import type { FlowPoint } from '../overview-animated-flow-line-rendering';
import { pointAt, segmentClearanceKm } from './geometry';
import type { PropagationResult } from './types';

interface Node {
  index: number;
  left: Node | null;
  right: Node | null;
  lo: number[];
  hi: number[];
  minId: number;
}
/** Balanced k-d tree. Queries retain only eight admissible candidates. */
export class OrbitalSpatialIndex {
  private snapshot: PropagationResult;
  private root: Node | null;
  private cache = new Map<number, number[]>();
  readonly nodeCount: number;
  constructor(snapshot: PropagationResult) {
    this.snapshot = snapshot;
    const indices = snapshot.ids
      .map((_, i) => i)
      .filter((i) => snapshot.valid[i] === 1);
    this.nodeCount = indices.length;
    this.root = this.build(indices, 0);
  }
  private build(indices: number[], depth: number): Node | null {
    if (!indices.length) return null;
    const axis = depth % 3;
    indices.sort(
      (a, b) =>
        this.snapshot.positionsKm[a * 3 + axis] -
          this.snapshot.positionsKm[b * 3 + axis] ||
        Number(this.snapshot.ids[a]) - Number(this.snapshot.ids[b])
    );
    const middle = indices.length >> 1,
      index = indices[middle],
      p = pointAt(this.snapshot, index);
    const left = this.build(indices.slice(0, middle), depth + 1),
      right = this.build(indices.slice(middle + 1), depth + 1);
    const lo = [...p],
      hi = [...p];
    let minId = Number(this.snapshot.ids[index]);
    for (const child of [left, right])
      if (child) {
        minId = Math.min(minId, child.minId);
        for (let a = 0; a < 3; a++) {
          lo[a] = Math.min(lo[a], child.lo[a]);
          hi[a] = Math.max(hi[a], child.hi[a]);
        }
      }
    return { index, left, right, lo, hi, minId };
  }
  neighbors(index: number): number[] {
    const cached = this.cache.get(index);
    if (cached) return cached;
    const origin = pointAt(this.snapshot, index),
      best: { index: number; distance: number }[] = [];
    const lower = (node: Node) =>
      origin.reduce(
        (sum, v, i) => sum + Math.max(node.lo[i] - v, 0, v - node.hi[i]) ** 2,
        0
      );
    const visit = (node: Node | null): void => {
      if (!node) return;
      const bound = lower(node),
        last = best[7],
        cutoff = last?.distance ?? 25_000_000;
      if (
        bound > Math.min(cutoff, 25_000_000) ||
        (last &&
          bound === cutoff &&
          node.minId > Number(this.snapshot.ids[last.index]))
      )
        return;
      const point: FlowPoint = pointAt(this.snapshot, node.index),
        squared = point.reduce((sum, v, i) => sum + (v - origin[i]) ** 2, 0);
      if (
        node.index !== index &&
        squared <= 25_000_000 &&
        segmentClearanceKm(origin, point) >= 80 - 1e-9
      ) {
        best.push({ index: node.index, distance: squared });
        best.sort(
          (a, b) =>
            a.distance - b.distance ||
            Number(this.snapshot.ids[a.index]) -
              Number(this.snapshot.ids[b.index])
        );
        if (best.length > 8) best.pop();
      }
      const children = [node.left, node.right]
        .filter((n): n is Node => Boolean(n))
        .sort((a, b) => lower(a) - lower(b) || a.minId - b.minId);
      for (const child of children) visit(child);
    };
    visit(this.root);
    const result = best.map((entry) => entry.index);
    this.cache.set(index, result);
    return result;
  }
}
