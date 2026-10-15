import * as THREE from 'three';
import { useLayoutEffect, useMemo, useSyncExternalStore } from 'react';
import {
  activeFeatures,
  type AviationAdvisory,
} from '@/services/aviation-features';
import type { RouteSigmetEntry } from '@/services/route-sigmets';
import type { RouteSigmetSourceView } from './route-sigmet-source';
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
};
export type SigmetPresentation = {
  view: AviationLayerView;
  notices: SigmetNotice[];
  pendingCount: number;
  unknownCount: number;
  statusText: string;
  routeLabel: string;
  highlightUnavailable: boolean;
  dispose(): void;
};
const position = (entry: RouteSigmetEntry) =>
  entry.spans.reduce(
    (first, span) => Math.min(first, span.segment_index + span.start_fraction),
    Infinity
  );
const colors = ['#7dd3fc', '#f0abfc', '#fde68a'];

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
  const pending = entries
    .filter((entry) => !entry.acknowledged)
    .sort(
      (a, b) =>
        b.attention_order - a.attention_order ||
        position(a) - position(b) ||
        a.bulletin_key.localeCompare(b.bulletin_key) ||
        a.notice_key.localeCompare(b.notice_key)
    );
  const unknown = new Set(
    compatible ? snapshot!.unresolved.map((item) => item.feature_id) : []
  );
  const notices = pending.slice(0, 3).map((entry, index) => {
    const selected = entry.feature_ids.map((id) => byId.get(id)!);
    const p = selected[0].properties;
    return {
      entry,
      reports: selected,
      label: `${p.issuer ?? 'Unknown issuer'} ${p.series ?? 'unknown series'} · ${entry.bulletin_key.slice(0, 8)}`,
      color: colors[index],
      intersectionUnknown: entry.feature_ids.some((id) => unknown.has(id)),
    };
  });
  const stale =
    product?.state === 'stale' ||
    snapshot?.status === 'stale' ||
    !!source.error ||
    (product?.fresh_until_ms != null && nowMs >= product.fresh_until_ms);
  return {
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
      : { state: source.error ? 'unavailable' : 'loading' },
    notices,
    pendingCount: pending.length,
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
  const object = new THREE.Group();
  object.name = 'Native route SIGMET presentation';
  try {
    const base = createBudgetedAviationDrawing(
      data,
      'sigmet',
      input.nowMs,
      budget
    );
    drawings.push(base);
    object.add(base.object);
  } catch {
    presentation.highlightUnavailable = true;
    return presentation;
  }
  for (const notice of presentation.notices) {
    try {
      const highlight = createSigmetHighlights(
        notice,
        input.routePoints,
        budget
      );
      drawings.push(highlight);
      object.add(highlight.object);
    } catch {
      presentation.highlightUnavailable = true;
    }
  }
  presentation.view.drawing = {
    object,
    bytes: drawings.reduce((sum, drawing) => sum + drawing.bytes, 0),
    featureAt: () => undefined,
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
