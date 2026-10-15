import * as THREE from 'three';
import { useLayoutEffect, useMemo, useSyncExternalStore } from 'react';
import {
  activeFeatures,
  type AviationAdvisory,
} from '@/services/aviation-features';
import type { RouteSigmetEntry } from '@/services/route-sigmets';
import type { RouteSigmetSourceView } from './route-sigmet-source';
import {
  sigmetAttentionItems,
  type SigmetAttentionItem,
} from './sigmet-attention';
import { optionalWeatherBudget, type WeatherBudget } from './weather-budget';
import type { AviationLayerView } from './aviation-controller';
import {
  createBudgetedAviationDrawing,
  type AviationDrawing,
} from './aviation-renderer';
import {
  createSigmetHighlights,
  type SigmetNotice,
  type SigmetRoutePoint,
} from './route-sigmet-highlights';

export type SigmetPresentationInput = {
  source: RouteSigmetSourceView;
  localContextKey: string | null;
  intersectingOnly: boolean;
  nowMs: number;
  /** Borrowed from Overview's selected route; never a duplicate route buffer. */
  routePoints: readonly SigmetRoutePoint[];
  attentionPage?: number;
};
export type SigmetMapLabel = {
  id: string;
  text: string;
  color: string;
  position: [number, number, number];
};
export type SigmetPresentation = {
  mapLabels: SigmetMapLabel[];
  view: AviationLayerView;
  notices: (SigmetNotice & { entry: RouteSigmetEntry })[];
  attentionItems: SigmetAttentionItem[];
  visibleItems: SigmetAttentionItem[];
  pendingCount: number;
  unknownCount: number;
  statusText: string;
  routeLabel: string;
  highlightUnavailable: boolean;
  dispose(): void;
};

function describe(input: SigmetPresentationInput): SigmetPresentation {
  const { source, localContextKey, intersectingOnly, nowMs } = input;
  const snapshot = source.snapshot,
    product = snapshot?.sigmet_product;
  const bound = !!(
    source.available &&
    source.collection &&
    source.dataLease &&
    product &&
    product.expires_at_ms !== null &&
    nowMs < product.expires_at_ms &&
    ['ready', 'stale'].includes(product.state) &&
    source.collection.retrieved_at_ms === product.retrieved_at_ms &&
    source.collection.source_id === product.source_id
  );
  const compatible = !!(
    bound &&
    localContextKey &&
    snapshot?.context?.context_key === localContextKey &&
    ['ready', 'stale', 'incomplete'].includes(snapshot.status)
  );
  const reports = bound
    ? (activeFeatures(
        source.collection!,
        'sigmet',
        nowMs
      ) as AviationAdvisory[])
    : [];
  const byId = new Map(reports.map((report) => [report.id, report]));
  const entries = compatible
    ? snapshot!.entries.filter(
        (entry) =>
          entry.valid_from_ms <= nowMs &&
          nowMs < entry.expires_at_ms &&
          entry.feature_ids.every((id) => byId.has(id))
      )
    : [];
  const matched = new Set(entries.flatMap((entry) => entry.feature_ids));
  const unknown = new Set(
    compatible ? snapshot!.unresolved.map((item) => item.feature_id) : []
  );
  const stale =
    product?.state === 'stale' ||
    snapshot?.status === 'stale' ||
    !!source.error ||
    (product?.fresh_until_ms != null && nowMs >= product.fresh_until_ms);
  const attentionItems = sigmetAttentionItems(
    compatible ? snapshot : null,
    reports,
    nowMs
  );
  const page = Math.min(
    Math.max(0, input.attentionPage ?? 0),
    Math.max(0, Math.ceil(attentionItems.length / 3) - 1)
  );
  const visibleItems = attentionItems.slice(page * 3, page * 3 + 3);
  const notices = visibleItems
    .filter(
      (
        item
      ): item is SigmetAttentionItem & {
        kind: 'intersecting';
        entry: RouteSigmetEntry;
      } => item.kind === 'intersecting'
    )
    .map((item) => ({
      ...item,
      intersectionUnknown: item.entry.feature_ids.some((id) => unknown.has(id)),
    }));
  return {
    mapLabels: [],
    attentionItems,
    visibleItems,
    view: bound
      ? {
          state: stale ? 'stale' : 'current',
          product,
          data: {
            ...source.collection!,
            features: intersectingOnly
              ? reports.filter((report) => matched.has(report.id))
              : reports,
          },
        }
      : {
          state:
            source.error || product?.state === 'unavailable'
              ? 'unavailable'
              : 'loading',
        },
    notices,
    pendingCount: attentionItems.length,
    unknownCount: unknown.size,
    statusText: !localContextKey
      ? 'Route unavailable · route intersection unknown'
      : !compatible
        ? 'Route evaluation unavailable or loading · route intersection unknown'
        : `${snapshot!.status}${stale ? ' · stale' : ''}${!snapshot!.complete ? ' · Some route intersections unknown' : ''}`,
    routeLabel: compatible
      ? `${snapshot!.context!.route_name || 'Unnamed route'} · ${snapshot!.context!.source === 'simulation' ? 'Simulation route' : 'Ordinary route'}`
      : '',
    highlightUnavailable: false,
    dispose() {},
  };
}

/** The presentation owns GPU resources and releases them before its retained source data. */
export function createSigmetPresentation(
  input: SigmetPresentationInput,
  budget: WeatherBudget = optionalWeatherBudget
): SigmetPresentation {
  const presentation = describe(input),
    drawings: AviationDrawing[] = [];
  const lease = presentation.view.data?.features.length
    ? input.source.dataLease?.retain()
    : undefined;
  let owned = true;
  presentation.dispose = () => {
    if (!owned) return;
    owned = false;
    drawings.forEach((drawing) => drawing.dispose());
    lease?.release();
  };
  const data = presentation.view.data;
  if (!data?.features.some((feature) => feature.geometry)) {
    presentation.highlightUnavailable = presentation.notices.length > 0;
    return presentation;
  }
  let featureAt: AviationDrawing['featureAt'] = () => undefined;
  const object = new THREE.Group();
  object.name = 'Native route SIGMET presentation';
  // Read-only diagnostics follow the native GFS owner convention.
  object.userData.routeSigmetBudget = () => budget.snapshot();
  try {
    const base = createBudgetedAviationDrawing(
      data,
      'sigmet',
      input.nowMs,
      budget
    );
    featureAt = base.featureAt;
    drawings.push(base);
    object.add(base.object);
  } catch {
    presentation.highlightUnavailable = true;
    return presentation;
  }
  for (const notice of presentation.visibleItems) {
    try {
      const highlight = createSigmetHighlights(
        notice,
        input.routePoints,
        budget
      );
      presentation.mapLabels.push({
        id: `sigmet:${notice.entry.notice_key}`,
        text: notice.label,
        color: notice.color,
        position: highlight.labelPosition,
      });
      drawings.push(highlight);
      object.add(highlight.object);
    } catch {
      presentation.highlightUnavailable = true;
    }
  }
  presentation.view.drawing = {
    object,
    bytes: drawings.reduce((sum, drawing) => sum + drawing.bytes, 0),
    featureAt,
    dispose: presentation.dispose,
  };
  return presentation;
}

function presentationBinding() {
  let current: {
    input: SigmetPresentationInput;
    presentation: SigmetPresentation;
  } | null = null;
  const listeners = new Set<() => void>();
  const emit = () => {
    for (const listener of listeners) listener();
  };
  return {
    snapshot: () => current,
    subscribe: (listener: () => void) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    attach: (
      input: SigmetPresentationInput,
      presentation: SigmetPresentation
    ) => {
      current = { input, presentation };
      emit();
      return () => {
        presentation.dispose();
        if (current?.presentation === presentation) {
          current = null;
          emit();
        }
      };
    },
  };
}

/** Allocation occurs only after commit; abandoned React renders cannot own GPU buffers. */
export function useSigmetPresentation(
  input: SigmetPresentationInput,
  enabled: boolean,
  budget: WeatherBudget = optionalWeatherBudget
) {
  const binding = useMemo(() => presentationBinding(), []);
  const owned = useSyncExternalStore(binding.subscribe, binding.snapshot);
  const fallback = useMemo(() => describe(input), [input]);
  useLayoutEffect(() => {
    if (!enabled) return;
    return binding.attach(input, createSigmetPresentation(input, budget));
  }, [binding, input, enabled, budget]);
  return enabled && owned?.input === input ? owned.presentation : fallback;
}
