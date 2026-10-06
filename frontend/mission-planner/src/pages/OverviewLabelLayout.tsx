import { useEffect, useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import {
  calloutLeader,
  type OverviewLabelLayoutResult,
  type OverviewLabelOffset,
  type LabelPoint,
} from './overview-label-layout';
import {
  applyOverviewLabelLayout,
  positionOverviewDisclosure,
} from './overview-label-dom';
import type {
  LabelLayoutRequest,
  LabelLayoutResponse,
} from './overview-label-layout.worker';

interface Snapshot {
  request: LabelLayoutRequest;
  stage: HTMLElement;
  anchors: Record<string, LabelPoint>;
  pinned: OverviewLabelLayoutResult;
}

/** Html projects the anchors every frame. Measure all label types together at
 * most ten times a second. Solve collisions off the render thread, coalescing
 * pending camera snapshots; valid offsets continue following the Html anchors.
 */
export function OverviewLabelLayout() {
  const gl = useThree((state) => state.gl);
  const previous = useRef<Record<string, OverviewLabelOffset>>({});
  const last = useRef({ time: -Infinity, signature: '', revision: 0 });
  const worker = useRef<Worker | null>(null);
  const pending = useRef<Snapshot | null>(null);
  const queued = useRef<Snapshot | null>(null);
  useEffect(() => {
    const instance = new Worker(
      new URL('./overview-label-layout.worker.ts', import.meta.url),
      { type: 'module' }
    );
    worker.current = instance;
    last.current.signature = '';
    instance.onmessage = ({ data }: MessageEvent<LabelLayoutResponse>) => {
      const snapshot = pending.current;
      if (!snapshot || snapshot.request.revision !== data.revision) return;
      const layout = {
        offsets: { ...data.layout.offsets, ...snapshot.pinned.offsets },
        placements: {
          ...data.layout.placements,
          ...snapshot.pinned.placements,
        },
        groups: [...data.layout.groups, ...snapshot.pinned.groups],
      };
      const openGroups = [
        ...snapshot.stage.querySelectorAll<HTMLDetailsElement>(
          '.overview-label-group[open]'
        ),
      ]
        .filter(
          (details) =>
            details.closest<HTMLElement>('[data-overview-label-id]')?.dataset
              .labelInView !== 'false'
        )
        .map((details) => [
          details.closest<HTMLElement>('[data-overview-label-id]')!.dataset
            .overviewLabelId,
          details.dataset.groupIds,
        ]);
      const expectedGroups = snapshot.pinned.groups.map((group) => [
        group.anchorId,
        JSON.stringify(group.ids),
      ]);
      // Camera offsets may lag by a snapshot; disclosure interaction may not.
      // A response measured before opening/closing a list cannot regroup its
      // focused control. The coalesced request (or next frame) uses current state.
      if (
        JSON.stringify(openGroups.sort()) ===
        JSON.stringify(expectedGroups.sort())
      ) {
        previous.current = layout.offsets;
        applyOverviewLabelLayout(snapshot.stage, layout, snapshot.anchors);
      } else last.current.signature = '';
      pending.current = queued.current;
      queued.current = null;
      if (pending.current) {
        pending.current.request.previous = previous.current;
        instance.postMessage(pending.current.request);
      }
    };
    return () => {
      instance.terminate();
      worker.current = null;
      pending.current = null;
      queued.current = null;
    };
  }, []);
  useFrame((state) => {
    const time = state.clock.elapsedTime;
    if (time - last.current.time < 0.1) return;
    last.current.time = time;
    const stage = gl.domElement.closest<HTMLElement>('.overview-map-stage');
    if (!stage || !worker.current) return;
    const viewport = gl.domElement.getBoundingClientRect();
    const anchors: Record<string, LabelPoint> = {};
    const labels = [
      ...stage.querySelectorAll<HTMLElement>('[data-overview-label-id]'),
    ].flatMap((root) => {
      const source = root.querySelector<HTMLElement>('[data-label-source]')!;
      const point = root.getBoundingClientRect();
      const x = point.x - viewport.x,
        y = point.y - viewport.y;
      // Occluded Html has no layout box. Off-screen anchors are not pulled back
      // into view by the collision solver; their whole callout disappears.
      const visible =
        source.offsetWidth > 0 &&
        x >= 0 &&
        y >= 0 &&
        x <= viewport.width &&
        y <= viewport.height;
      root.dataset.labelInView = String(visible);
      root.style.visibility = visible ? 'visible' : 'hidden';
      if (!visible) {
        source.style.visibility = 'hidden';
        return [];
      }
      const id = root.dataset.overviewLabelId!;
      anchors[id] = { x, y };
      return [
        {
          id,
          text: root.dataset.labelText,
          bounds: {
            x,
            y,
            width: source.offsetWidth,
            height: source.offsetHeight,
          },
          retainIdentity: root.dataset.labelRetainIdentity === 'true',
          priority: Number(root.dataset.labelPriority) || 0,
        },
      ];
    });
    // Keep an open disclosure anchored while the rest of the labels move clear
    // of its summary and list. This avoids regrouping the control under focus.
    const pinned: OverviewLabelLayoutResult = {
      offsets: {},
      placements: {},
      groups: [],
    };
    const pinnedIds = new Set<string>();
    const popupBounds = [
      ...stage.querySelectorAll<HTMLDetailsElement>(
        '.overview-label-group[open]'
      ),
    ].flatMap((details) => {
      positionOverviewDisclosure(details);
      const root = details.closest<HTMLElement>('[data-overview-label-id]')!;
      const id = root.dataset.overviewLabelId!;
      const ids: string[] = JSON.parse(details.dataset.groupIds ?? '[]');
      const anchor = anchors[id];
      if (!anchor || !ids.length) return [];
      const boxes = ['summary', 'ul'].map((selector) => {
        const box = details.querySelector(selector)!.getBoundingClientRect();
        return {
          x: box.x - viewport.x,
          y: box.y - viewport.y,
          width: box.width,
          height: box.height,
        };
      });
      pinned.offsets[id] = [boxes[0].x - anchor.x, boxes[0].y - anchor.y];
      pinned.placements[id] = {
        bounds: boxes[0],
        leader: calloutLeader(anchor, boxes[0]),
      };
      pinned.groups.push({ anchorId: id, ids });
      ids.forEach((member) => pinnedIds.add(member));
      return boxes;
    });
    const reserved = [
      ...(
        stage.closest('.overview-page') ?? stage
      ).querySelectorAll<HTMLElement>(
        '.overview-planned-satellite,.overview-arrival,.globe-legend,.overview-fullscreen-control,.overview-map-status,.overview-map-controls,.overview-top-overlays,.overview-metrics-overlays,.overview-display-label,.overview-marker-debug'
      ),
    ].flatMap((node) => {
      const box = node.getBoundingClientRect();
      return box.width && box.height
        ? [
            {
              x: box.x - viewport.x,
              y: box.y - viewport.y,
              width: box.width,
              height: box.height,
            },
          ]
        : [];
    });
    reserved.push(...popupBounds);
    for (const id of pinnedIds) {
      const anchor = anchors[id];
      if (anchor)
        reserved.push({
          x: anchor.x - 4,
          y: anchor.y - 4,
          width: 8,
          height: 8,
        });
    }
    const signature = JSON.stringify([
      labels.map((l) => ({
        ...l,
        bounds: {
          ...l.bounds,
          x: Math.round(l.bounds.x),
          y: Math.round(l.bounds.y),
        },
      })),
      reserved,
      pinned.groups,
      viewport.width,
      viewport.height,
    ]);
    if (signature === last.current.signature) return;
    last.current.signature = signature;
    const snapshot: Snapshot = {
      request: {
        revision: ++last.current.revision,
        labels: labels.filter((label) => !pinnedIds.has(label.id)),
        viewport: { width: viewport.width, height: viewport.height },
        reserved,
        previous: previous.current,
      },
      stage,
      anchors,
      pinned,
    };
    if (pending.current) queued.current = snapshot;
    else {
      pending.current = snapshot;
      worker.current.postMessage(snapshot.request);
    }
  });
  return null;
}
