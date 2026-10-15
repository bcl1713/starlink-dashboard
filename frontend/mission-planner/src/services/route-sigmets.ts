import { z } from 'zod';
import { weatherProductSchema } from './aviation-weather';
import type { WeatherFetcher } from './aviation-grid';
import {
  abortable,
  weatherKey,
  type Reservation,
  type WeatherBudget,
} from '@/pages/aviation-weather/weather-budget';

const integer = z.number().int().nonnegative().max(Number.MAX_SAFE_INTEGER);
const hash = z.string().regex(/^[a-f0-9]{64}$/);
const text = (max: number, min = 0) =>
  z.string().refine((v) => [...v].length >= min && [...v].length <= max);
const id = text(256, 1);
const position = z.tuple([
  z.number().finite().min(-180).max(180),
  z.number().finite().min(-90).max(90),
]);
export const routeContextSchema = z
  .strictObject({
    context_key: hash,
    source: z.enum(['ordinary', 'simulation']),
    route_id: id,
    route_name: text(512),
    runtime_id: id.nullable(),
    run_id: id.nullable(),
  })
  .refine((c) =>
    c.source === 'simulation'
      ? c.runtime_id !== null && c.run_id !== null
      : c.runtime_id === null && c.run_id === null
  );
export const intersectionSpanSchema = z
  .strictObject({
    segment_index: integer,
    start_fraction: z.number().min(0).max(1),
    end_fraction: z.number().min(0).max(1),
    entry: position,
    exit: position,
    boundary_error_m: z.number().min(0).max(18.52),
  })
  .refine((s) => s.start_fraction <= s.end_fraction);
const unique = (values: string[]) => new Set(values).size === values.length;
const entryFields = {
  selected: z.boolean().default(false),
  notice_key: hash,
  bulletin_key: hash,
  semantic_digest: hash,
  feature_ids: z.array(id).min(1).max(500),
  attention_order: integer,
  acknowledged: z.boolean(),
  valid_from_ms: integer,
  expires_at_ms: integer,
  identity_uncertain: z.boolean(),
};
export const selectedSigmetEntrySchema = z
  .strictObject(entryFields)
  .refine((e) => unique(e.feature_ids) && e.valid_from_ms < e.expires_at_ms);
const passageReason = z.enum([
  'missing-timing',
  'invalid-timing',
  'ambiguous-association',
  'unavailable-plan',
]);
const passageStatus = z.enum(['overlap', 'no-overlap', 'unknown']);
const passageSchema = z
  .strictObject({
    entry_ms: integer.nullable(),
    exit_ms: integer.nullable(),
    status: passageStatus,
    reason: passageReason.nullable(),
  })
  .refine((p) =>
    p.status === 'unknown'
      ? p.entry_ms === null && p.exit_ms === null && p.reason !== null
      : p.entry_ms !== null &&
        p.exit_ms !== null &&
        p.entry_ms <= p.exit_ms &&
        p.reason === null
  );
const encounterSchema = z
  .strictObject({
    spans: z.array(passageSchema).min(1).max(100000),
    status: passageStatus,
    unknown_count: integer,
    reason: passageReason.nullable(),
  })
  .refine((e) => {
    const unknown = e.spans.filter((p) => p.status === 'unknown').length;
    const status = e.spans.some((p) => p.status === 'overlap')
      ? 'overlap'
      : unknown
        ? 'unknown'
        : 'no-overlap';
    const reason =
      status === 'unknown'
        ? (e.spans.find((p) => p.reason)?.reason ?? null)
        : null;
    return (
      e.status === status && e.unknown_count === unknown && e.reason === reason
    );
  });
export const encounterPlanSchema = z.strictObject({
  revision: hash,
  method: z.literal('segment-linear-utc-v1'),
  source: z.enum(['ordinary', 'simulation']),
  source_revision: text(256).nullable(),
  precision: z.enum(['minute', 'second', 'unknown']),
});
export type EncounterPlanSummary = z.infer<typeof encounterPlanSchema>;
export const routeSigmetEntrySchema = z
  .strictObject({
    ...entryFields,
    spans: z.array(intersectionSpanSchema).min(1).max(100000),
    encounter: encounterSchema,
  })
  .refine(
    (e) =>
      unique(e.feature_ids) &&
      e.valid_from_ms < e.expires_at_ms &&
      e.spans.length === e.encounter.spans.length &&
      e.encounter.spans.every(
        (p) =>
          p.status === 'unknown' ||
          (p.exit_ms! >= e.valid_from_ms && p.entry_ms! < e.expires_at_ms) ===
            (p.status === 'overlap')
      )
  );
const unresolved = z.strictObject({
  feature_id: id,
  reason: z.enum([
    'unlocated',
    'boundary-uncertain',
    'identity-uncertain',
    'invalid-route',
    'limit',
  ]),
});
export const routeSigmetSnapshotSchema = z
  .strictObject({
    schema: z.literal('route-sigmets-v2'),
    service_instance_id: z.string().regex(/^[a-f0-9]{32}$/),
    observation_revision: integer,
    encounter_plan: encounterPlanSchema.nullable(),
    generated_at_ms: integer,
    settings_revision: integer,
    state_revision: integer,
    generation_id: hash,
    context: routeContextSchema.nullable(),
    sigmet_product: weatherProductSchema,
    status: z.enum([
      'off',
      'no-route',
      'evaluating',
      'ready',
      'stale',
      'incomplete',
      'unavailable',
    ]),
    reason: text(512).nullable(),
    complete: z.boolean(),
    truncated: z.literal(false),
    entries: z.array(routeSigmetEntrySchema).max(500),
    selected_entries: z.array(selectedSigmetEntrySchema).max(500).default([]),
    selection_candidates: z
      .array(
        z.strictObject({
          bulletin_key: hash,
          semantic_digest: hash,
          feature_ids: z.array(id).min(1).max(500),
        })
      )
      .max(500)
      .default([]),
    unresolved: z.array(unresolved).max(500),
    future_feature_ids: z.array(id).max(500),
    omitted_features: integer,
  })
  .refine((s) => {
    const entries = [...s.entries, ...s.selected_entries];
    const features = entries.flatMap((e) => e.feature_ids);
    const candidates = s.selection_candidates.flatMap((e) => e.feature_ids);
    return (
      (s.context !== null || s.encounter_plan === null) &&
      (!s.encounter_plan || s.context?.source === s.encounter_plan.source) &&
      unique(entries.map((e) => e.notice_key)) &&
      unique(entries.map((e) => e.bulletin_key)) &&
      unique(features) &&
      unique(candidates) &&
      unique(s.selection_candidates.map((e) => e.bulletin_key)) &&
      unique(s.unresolved.map((e) => e.feature_id)) &&
      unique(s.future_feature_ids) &&
      new Set([
        ...features,
        ...candidates,
        ...s.unresolved.map((e) => e.feature_id),
        ...s.future_feature_ids,
      ]).size <= 500 &&
      s.entries.reduce((n, e) => n + e.spans.length, 0) <= 100000 &&
      (!s.complete || (!s.unresolved.length && !s.omitted_features)) &&
      (s.status !== 'ready' || s.complete) &&
      (!entries.length || s.context !== null) &&
      s.sigmet_product.product_type === 'international-sigmet' &&
      new TextEncoder().encode(JSON.stringify(s)).length <= 8 * 1024 ** 2
    );
  });
export const noticeSelectionSchema = z.strictObject({
  context_key: hash,
  bulletin_key: hash,
  semantic_digest: hash,
});
export type NoticeSelection = z.infer<typeof noticeSelectionSchema>;
export type SelectedSigmetEntry = z.infer<typeof selectedSigmetEntrySchema>;
export const noticeMutationSchema = z.strictObject({
  context_key: hash,
  notice_key: hash,
  semantic_digest: hash,
  acknowledged: z.boolean(),
});
export const noticeConfirmationSchema = noticeMutationSchema.extend({
  state_revision: integer,
  attention_order: integer,
});
export type WireRouteContext = z.infer<typeof routeContextSchema>;
export type IntersectionSpan = z.infer<typeof intersectionSpanSchema>;
export type RouteSigmetEntry = z.infer<typeof routeSigmetEntrySchema>;
export type RouteSigmetSnapshot = z.infer<typeof routeSigmetSnapshotSchema>;
export type NoticeMutation = z.infer<typeof noticeMutationSchema>;
export type NoticeConfirmation = z.infer<typeof noticeConfirmationSchema>;
export const parseRouteSigmetSnapshot = (data: unknown) =>
  routeSigmetSnapshotSchema.parse(data);
export const parseNoticeMutation = (data: unknown) =>
  noticeMutationSchema.parse(data);
export const parseNoticeConfirmation = (data: unknown) =>
  noticeConfirmationSchema.parse(data);
export const routeSigmetsKey = ['aviation-weather', 'route-sigmets'] as const;
export class RouteSigmetHttpError extends Error {
  readonly status: number;
  constructor(status: number) {
    super(`Route SIGMET request failed (${status})`);
    this.status = status;
  }
}

/** Response scratch and retained decoded data are both reserved before decoding. */
async function jsonLease<T>(
  path: string,
  init: RequestInit,
  signal: AbortSignal,
  budget: WeatherBudget,
  fetcher: WeatherFetcher,
  parse: (data: unknown) => T,
  max: number
) {
  const slot = await budget.acquire(signal);
  const raw: Reservation[] = [];
  let allocation: Reservation | undefined;
  let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
  let admitted = false;
  try {
    const response = await abortable(
      fetcher(path, {
        ...init,
        signal,
        credentials: 'same-origin',
        cache: 'no-store',
        redirect: 'error',
      }),
      signal
    );
    if (!response.ok) throw new RouteSigmetHttpError(response.status);
    if (
      !response.body ||
      response.headers.get('Content-Type')?.split(';')[0].trim() !==
        'application/json'
    )
      throw Error('Invalid route SIGMET response');
    const length = response.headers.get('Content-Length');
    if (length !== null && (!/^\d+$/.test(length) || Number(length) > max))
      throw Error('Route SIGMET response size');
    // Fetch exposes decompressed bytes; a compressed Content-Length is not
    // their size. Nginx also omits length entirely on streamed gzip responses.
    const exact = length !== null && !response.headers.get('Content-Encoding');
    const limit = exact ? Number(length) : max;
    reader = response.body.getReader();
    const parts: Uint8Array[] = [];
    let size = 0,
      used = 0;
    while (true) {
      const { done, value } = await abortable(reader.read(), signal);
      if (done) break;
      if (size + value.byteLength > limit)
        throw Error('Route SIGMET response size');
      let offset = 0;
      while (offset < value.byteLength) {
        if (!parts.length || used === parts[parts.length - 1].length) {
          // Fixed slabs bound metadata even if the server emits tiny chunks.
          // Reserve before allocation, including retained slabs plus final join.
          const capacity = Math.min(65536, limit - size);
          raw.push(
            budget.reserve(weatherKey('route-transfer'), {
              encoded: capacity * 2,
              decoded: capacity * 2,
              gpu: 0,
            })
          );
          parts.push(new Uint8Array(capacity));
          used = 0;
        }
        const block = parts[parts.length - 1];
        const count = Math.min(value.byteLength - offset, block.length - used);
        block.set(value.subarray(offset, offset + count), used);
        used += count;
        size += count;
        offset += count;
      }
    }
    if (exact && size !== limit) throw Error('Route SIGMET response size');
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const part of parts) {
      const count = Math.min(part.length, size - offset);
      bytes.set(part.subarray(0, count), offset);
      offset += count;
    }
    parts.length = 0;
    const key = weatherKey('route-data');
    const amounts = { encoded: 0, decoded: size * 4, gpu: 0 };
    allocation = budget.reserve(key, amounts);
    const data = parse(
      JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes))
    );
    signal.throwIfAborted();
    admitted = true;
    return { data, allocation, retain: () => budget.reserve(key, amounts) };
  } finally {
    if (!admitted) allocation?.release();
    raw.forEach((reservation) => reservation.release());
    if (reader) {
      void reader.cancel().catch(() => {});
      reader.releaseLock();
    }
    slot();
  }
}
export function readRouteSigmetSnapshot(
  signal: AbortSignal,
  budget: WeatherBudget,
  fetcher: WeatherFetcher = fetch
) {
  return jsonLease(
    '/api/aviation-weather/v1/route-sigmets',
    {},
    signal,
    budget,
    fetcher,
    parseRouteSigmetSnapshot,
    8 * 1024 ** 2
  );
}
export async function setSigmetAcknowledgement(
  change: NoticeMutation,
  signal: AbortSignal,
  budget: WeatherBudget,
  fetcher: WeatherFetcher = fetch
) {
  const result = await jsonLease(
    '/api/aviation-weather/v1/route-sigmets/acknowledgement',
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(parseNoticeMutation(change)),
    },
    signal,
    budget,
    fetcher,
    parseNoticeConfirmation,
    65536
  );
  result.allocation.release();
  return result.data;
}

export async function setSigmetSelection(
  change: NoticeSelection,
  signal: AbortSignal,
  budget: WeatherBudget,
  fetcher: WeatherFetcher = fetch
) {
  const result = await jsonLease(
    '/api/aviation-weather/v1/route-sigmets/selection',
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(noticeSelectionSchema.parse(change)),
    },
    signal,
    budget,
    fetcher,
    parseRouteSigmetSnapshot,
    8 * 1024 ** 2
  );
  try {
    const snapshot = result.data;
    if (snapshot.context?.context_key !== change.context_key)
      throw Error('Obsolete SIGMET selection context');
    const selected = [...snapshot.entries, ...snapshot.selected_entries].find(
      (entry) =>
        entry.bulletin_key === change.bulletin_key &&
        entry.semantic_digest === change.semantic_digest &&
        !entry.acknowledged
    );
    return {
      context_key: change.context_key,
      state_revision: snapshot.state_revision,
      notice_key: selected?.notice_key ?? null,
    };
  } finally {
    result.allocation.release();
  }
}

export type SigmetSelectionConfirmation = Awaited<
  ReturnType<typeof setSigmetSelection>
>;
