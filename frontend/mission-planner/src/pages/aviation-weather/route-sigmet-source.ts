import { QueryClient, QueryObserver } from '@tanstack/react-query';
import type { AviationSettings } from '@/services/aviation-weather';
import type { AviationCollection } from '@/services/aviation-features';
import type { WeatherFetcher } from '@/services/aviation-grid';
import {
  readRouteSigmetSnapshot,
  setSigmetAcknowledgement,
  setSigmetSelection,
  type NoticeSelection,
  RouteSigmetHttpError,
  routeSigmetsKey,
  type RouteSigmetSnapshot,
  type NoticeMutation,
  type NoticeConfirmation,
} from '@/services/route-sigmets';
import { fetchAviationPayload } from './aviation-controller';
import {
  abortable,
  optionalWeatherBudget,
  weatherKey,
  type Reservation,
  type WeatherBudget,
} from './weather-budget';

export type RouteSigmetDataLease = { retain(): Reservation };
export type RouteSigmetSourceView = {
  snapshot: RouteSigmetSnapshot | null;
  collection: AviationCollection | null;
  available: boolean;
  error: Error | null;
  dataLease: RouteSigmetDataLease | null;
  nowMs: number;
};
const empty = (): RouteSigmetSourceView => ({
  snapshot: null,
  collection: null,
  available: false,
  error: null,
  dataLease: null,
  nowMs: 0,
});
/** One data owner per QueryClient. Query cache stores only a completion token. */
export class RouteSigmetSource {
  private listeners = new Set<() => void>();
  private observer: QueryObserver<null> | null = null;
  private unobserve: (() => void) | null = null;
  private settings: AviationSettings | undefined;
  private visible = typeof document === 'undefined' || !document.hidden;
  private online = typeof navigator === 'undefined' || navigator.onLine;
  private epoch = 0;
  private readOwner: AbortController | null = null;
  private writeOwner: AbortController | null = null;
  private writing = false;
  private writes: Promise<unknown> = Promise.resolve();
  private revision = 0;
  private confirmed = new Map<string, NoticeConfirmation>();
  private routeLease: Reservation | null = null;
  private payloadLease: Reservation | null = null;
  private payloadRetain: (() => Reservation) | null = null;
  private boundary: ReturnType<typeof setTimeout> | undefined;
  private anchor: { utc: number; mono: number } | null = null;
  private view = empty();
  private budget: WeatherBudget;
  private fetcher: WeatherFetcher;
  private client: QueryClient;
  constructor(
    client: QueryClient,
    options: { fetcher?: WeatherFetcher; budget?: WeatherBudget } = {}
  ) {
    this.budget = options.budget ?? optionalWeatherBudget;
    this.fetcher = options.fetcher ?? fetch;
    this.client = client;
  }
  snapshot = () => this.view;
  nowMs = () =>
    this.anchor
      ? this.anchor.utc + Math.max(0, performance.now() - this.anchor.mono)
      : 0;
  private active = () =>
    this.listeners.size > 0 &&
    this.visible &&
    this.online &&
    !!this.settings?.sigmet;
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    if (this.listeners.size === 1) {
      this.visible = typeof document === 'undefined' || !document.hidden;
      this.online = typeof navigator === 'undefined' || navigator.onLine;
      this.observer = new QueryObserver<null>(this.client, this.options());
      this.unobserve = this.observer.subscribe(() => {});
      if (typeof document !== 'undefined')
        document.addEventListener('visibilitychange', this.environment);
      if (typeof window !== 'undefined') {
        window.addEventListener('online', this.environment);
        window.addEventListener('offline', this.environment);
      }
    }
    let subscribed = true;
    return () => {
      if (!subscribed) return;
      subscribed = false;
      this.listeners.delete(listener);
      if (!this.listeners.size) this.dispose();
    };
  };
  private environment = () => {
    const visible = !document.hidden,
      online = navigator.onLine;
    if (this.visible === visible && this.online === online) return;
    this.visible = visible;
    this.online = online;
    this.reconcile();
  };
  private options() {
    const enabled = this.active();
    return {
      queryKey: routeSigmetsKey,
      queryFn: async ({ signal }: { signal: AbortSignal }) => {
        await this.read(signal);
        return null;
      },
      enabled,
      networkMode: 'always' as const,
      retry: false as const,
      gcTime: 0,
      refetchInterval: enabled ? 5000 : (false as const),
      refetchIntervalInBackground: true,
      refetchOnWindowFocus: false as const,
      refetchOnReconnect: false as const,
      structuralSharing: false as const,
    };
  }
  setSettings(next: AviationSettings | undefined) {
    if (!next || (this.settings && next.revision <= this.settings.revision))
      return;
    this.settings = next;
    this.reconcile();
  }
  setVisible(value: boolean) {
    if (value !== this.visible) {
      this.visible = value;
      this.reconcile();
    }
  }
  setOnline(value: boolean) {
    if (value !== this.online) {
      this.online = value;
      this.reconcile();
    }
  }
  private cancel(preserveBoundary = false) {
    this.epoch++;
    this.readOwner?.abort();
    this.readOwner = null;
    this.writeOwner?.abort();
    this.writeOwner = null;
    void this.client.cancelQueries({ queryKey: routeSigmetsKey, exact: true });
    if (!preserveBoundary) {
      if (this.boundary !== undefined) clearTimeout(this.boundary);
      this.boundary = undefined;
    }
  }
  private release() {
    this.routeLease?.release();
    this.routeLease = null;
    this.payloadLease?.release();
    this.payloadLease = null;
    this.payloadRetain = null;
  }
  private reconcile() {
    this.cancel();
    this.release();
    this.view = empty();
    this.emit();
    this.observer?.setOptions(this.options());
    if (this.active()) void this.refresh();
  }
  private emit() {
    for (const listener of this.listeners) listener();
  }
  private publish() {
    if (this.boundary !== undefined) clearTimeout(this.boundary);
    this.boundary = undefined;
    const now = this.nowMs(),
      snapshot = this.view.snapshot;
    if (
      snapshot &&
      snapshot.sigmet_product.expires_at_ms !== null &&
      now >= snapshot.sigmet_product.expires_at_ms
    ) {
      this.cancel();
      this.release();
      this.view = {
        ...empty(),
        nowMs: now,
        error: new Error('SIGMET product expired'),
      };
    } else {
      this.view = {
        ...this.view,
        nowMs: now,
        snapshot: snapshot
          ? {
              ...snapshot,
              entries: snapshot.entries.filter((e) => now < e.expires_at_ms),
              selected_entries: snapshot.selected_entries.filter((e) => now < e.expires_at_ms),
            }
          : null,
      };
      if (snapshot) {
        const boundaries = [
          snapshot.sigmet_product.fresh_until_ms,
          snapshot.sigmet_product.expires_at_ms,
          ...[...snapshot.entries, ...snapshot.selected_entries].flatMap((e) => [
            e.valid_from_ms,
            e.expires_at_ms,
          ]),
          ...(this.view.collection?.features.flatMap((f) => [
            f.properties.expires_at_ms,
            ...('valid_from_ms' in f.properties
              ? [f.properties.valid_from_ms]
              : []),
          ]) ?? []),
        ].filter((t): t is number => t !== null && t > now);
        if (boundaries.length)
          this.boundary = setTimeout(
            () => this.publish(),
            Math.min(2147483647, Math.max(1, Math.min(...boundaries) - now))
          );
      }
    }
    this.emit();
  }
  async refresh() {
    if (this.active() && this.observer && !this.writing)
      await this.observer.refetch({ cancelRefetch: true });
  }
  private async read(querySignal: AbortSignal) {
    if (!this.active() || this.writing) return;
    querySignal.throwIfAborted();
    const epoch = ++this.epoch,
      owner = new AbortController();
    this.readOwner?.abort();
    this.readOwner = owner;
    const abort = () => owner.abort();
    querySignal.addEventListener('abort', abort, { once: true });
    const deadline = setTimeout(
      () => owner.abort(new Error('Route SIGMET deadline')),
      10000
    );
    const current = () =>
      this.active() && epoch === this.epoch && !owner.signal.aborted;
    let route: Reservation | undefined,
      payload: Reservation | undefined,
      transfer: Reservation | undefined;
    try {
      const admitted = await readRouteSigmetSnapshot(
        owner.signal,
        this.budget,
        this.fetcher
      );
      route = admitted.allocation;
      let snapshot = admitted.data;
      if (!current()) return;
      // Non-materialized states have no notice-store revision. They are still
      // authoritative for this input epoch, but cannot reset acknowledgement
      // fences or resurrect notice state from a later obsolete GET.
      const noticeState = ['ready', 'stale', 'incomplete'].includes(
        snapshot.status
      );
      if (
        snapshot.settings_revision !== this.settings!.revision ||
        (noticeState && snapshot.state_revision < this.revision) ||
        (!noticeState && (snapshot.entries.length > 0 || snapshot.selected_entries.length > 0))
      )
        throw Error('Obsolete route SIGMET snapshot');
      this.anchor = {
        utc: Math.max(this.nowMs(), snapshot.generated_at_ms),
        mono: performance.now(),
      };
      snapshot = {
        ...snapshot,
        selected_entries: snapshot.selected_entries.filter(entry => {
          const ack = this.confirmed.get(entry.notice_key);
          return !(ack?.acknowledged && ack.context_key === snapshot.context?.context_key && ack.state_revision >= snapshot.state_revision);
        }),
        entries: snapshot.entries.map((entry) => {
          const confirmation = this.confirmed.get(entry.notice_key);
          return confirmation &&
            confirmation.context_key === snapshot.context?.context_key &&
            confirmation.semantic_digest === entry.semantic_digest &&
            confirmation.state_revision >= snapshot.state_revision
            ? {
                ...entry,
                acknowledged: confirmation.acknowledged,
                  selected: confirmation.acknowledged ? false : entry.selected,
                attention_order: confirmation.attention_order,
              }
            : entry;
        }),
      };
      for (const [key, confirmation] of this.confirmed) {
        if (
          noticeState &&
          (snapshot.state_revision > confirmation.state_revision ||
            confirmation.context_key !== snapshot.context?.context_key ||
            ![...snapshot.entries, ...snapshot.selected_entries].some(
              (e) =>
                e.notice_key === key &&
                e.semantic_digest === confirmation.semantic_digest
            ))
        )
          this.confirmed.delete(key);
      }
      this.revision = Math.max(this.revision, snapshot.state_revision);
      const product = snapshot.sigmet_product;
      const oldCollection = this.view.collection;
      const same =
        this.view.snapshot?.sigmet_product.instance_id ===
          product.instance_id && oldCollection !== null;
      this.routeLease?.release();
      this.routeLease = route;
      route = undefined;
      if (!same) {
        this.payloadLease?.release();
        this.payloadLease = null;
        this.payloadRetain = null;
      }
      const dataLease = () => {
        const retainPayload = this.payloadRetain;
        return {
          retain: () => {
            const route = admitted.retain();
            try {
              if (!retainPayload) throw Error('SIGMET data unavailable');
              const payload = retainPayload();
              return {
                release: () => {
                  payload.release();
                  route.release();
                },
              };
            } catch (error) {
              route.release();
              throw error;
            }
          },
        };
      };
      this.view = {
        snapshot,
        collection: same ? oldCollection : null,
        available: same,
        error: null,
        dataLease: same ? dataLease() : null,
        nowMs: this.nowMs(),
      };
      if (same && !this.bound(snapshot, oldCollection!)) {
        this.payloadLease?.release();
        this.payloadLease = null;
        this.payloadRetain = null;
        this.view = {
          ...this.view,
          collection: null,
          available: false,
          dataLease: null,
        };
        throw Error('SIGMET report generation mismatch');
      }
      this.publish();
      // Publish the new identity before loading, so old reports cannot bind to it.
      if (
        !product.payload ||
        !product.instance_id ||
        product.expires_at_ms === null ||
        this.nowMs() >= product.expires_at_ms ||
        product.layer_id !== 'sigmet'
      )
        return;
      if (!same) {
        if (product.payload.decoded_bytes < product.payload.encoded_bytes * 4)
          throw Error('Underdeclared SIGMET decoded allocation');
        const key = weatherKey('route-sigmet-collection');
        const amounts = {
          encoded: 0,
          decoded: product.payload.decoded_bytes,
          gpu: 0,
        };
        payload = this.budget.reserve(key, amounts);
        transfer = this.budget.reserve(weatherKey('route-sigmet-transfer'), {
          encoded: product.payload.encoded_bytes * 2,
          decoded: 0,
          gpu: 0,
        });
        const collection = await abortable(
          fetchAviationPayload(
            product,
            'sigmet',
            owner.signal,
            this.fetcher,
            this.budget
          ),
          owner.signal
        );
        transfer.release();
        transfer = undefined;
        if (!current()) return;
        if (!this.bound(snapshot, collection))
          throw Error('SIGMET report generation mismatch');
        this.payloadLease = payload;
        payload = undefined;
        this.payloadRetain = () => this.budget.reserve(key, amounts);
        this.view = {
          ...this.view,
          collection,
          available: true,
          dataLease: dataLease(),
        };
        this.publish();
      }
    } catch (error) {
      if (epoch === this.epoch && this.active()) {
        this.view = {
          ...this.view,
          error:
            error instanceof Error ? error : new Error('SIGMET unavailable'),
        };
        this.publish();
      }
    } finally {
      route?.release();
      payload?.release();
      transfer?.release();
      clearTimeout(deadline);
      querySignal.removeEventListener('abort', abort);
      owner.abort();
      if (this.readOwner === owner) this.readOwner = null;
    }
  }
  private bound(snapshot: RouteSigmetSnapshot, collection: AviationCollection) {
    const ids = new Set(collection.features.map((f) => f.id));
    return (
      collection.retrieved_at_ms === snapshot.sigmet_product.retrieved_at_ms &&
      collection.source_id === snapshot.sigmet_product.source_id &&
      [
        ...[...snapshot.entries, ...snapshot.selected_entries].flatMap((e) => e.feature_ids),
        ...snapshot.unresolved.map((u) => u.feature_id),
        ...snapshot.future_feature_ids,
      ].every((id) => ids.has(id))
    );
  }
  setSelection(change: NoticeSelection): Promise<RouteSigmetSnapshot> {
    const write = this.writes.then(() => this.select(change));
    this.writes = write.catch(() => {});
    return write;
  }
  private async select(change: NoticeSelection): Promise<RouteSigmetSnapshot> {
    const snapshot = this.view.snapshot;
    if (!this.active() || !snapshot || !this.view.available || snapshot.context?.context_key !== change.context_key)
      throw Error('SIGMET route is no longer current');
    this.cancel(true);
    this.writing = true;
    const epoch = this.epoch, owner = new AbortController();
    this.writeOwner = owner;
    const deadline = setTimeout(() => owner.abort(new Error('SIGMET selection deadline')), 10000);
    let conflict = false;
    try {
      await this.client.cancelQueries({queryKey: routeSigmetsKey, exact: true});
      if (!this.active() || epoch !== this.epoch || this.view.snapshot !== snapshot)
        throw Error('SIGMET route is no longer current');
      const result = await setSigmetSelection(change, owner.signal, this.budget, this.fetcher);
      if (!this.active() || epoch !== this.epoch || result.context?.context_key !== change.context_key || result.state_revision < this.revision)
        throw Error('Obsolete SIGMET selection');
      this.revision = result.state_revision;
      this.confirmed.clear();
      return result;
    } catch (error) {
      conflict = error instanceof RouteSigmetHttpError && error.status === 409;
      throw error;
    } finally {
      clearTimeout(deadline);
      if (this.writeOwner === owner) this.writeOwner = null;
      owner.abort();
      this.writing = false;
      if (this.active() && (epoch === this.epoch || conflict)) await this.refresh();
    }
  }
  setAcknowledgement(change: NoticeMutation): Promise<NoticeConfirmation> {
    const write = this.writes.then(() => this.write(change));
    this.writes = write.catch(() => {});
    return write;
  }
  private async write(change: NoticeMutation) {
    const snapshot = this.view.snapshot;
    if (
      !this.active() ||
      !snapshot ||
      snapshot.context?.context_key !== change.context_key ||
      ![...snapshot.entries, ...snapshot.selected_entries].some(
        (e) =>
          e.notice_key === change.notice_key &&
          e.semantic_digest === change.semantic_digest &&
          this.nowMs() >= e.valid_from_ms &&
          this.nowMs() < e.expires_at_ms
      )
    )
      throw Error('SIGMET notice is no longer current');
    this.cancel(true);
    this.writing = true;
    const epoch = this.epoch,
      owner = new AbortController();
    this.writeOwner = owner;
    const deadline = setTimeout(
      () => owner.abort(new Error('Route SIGMET deadline')),
      10000
    );
    let conflict = false;
    try {
      await this.client.cancelQueries({
        queryKey: routeSigmetsKey,
        exact: true,
      });
      if (
        !this.active() ||
        epoch !== this.epoch ||
        this.view.snapshot !== snapshot
      )
        throw Error('SIGMET notice is no longer current');
      const confirmation = await setSigmetAcknowledgement(
        change,
        owner.signal,
        this.budget,
        this.fetcher
      );
      if (
        !this.active() ||
        epoch !== this.epoch ||
        confirmation.state_revision < this.revision ||
        confirmation.context_key !== change.context_key ||
        confirmation.notice_key !== change.notice_key ||
        confirmation.semantic_digest !== change.semantic_digest ||
        confirmation.acknowledged !== change.acknowledged
      )
        throw Error('Obsolete SIGMET confirmation');
      this.revision = confirmation.state_revision;
      this.confirmed.set(change.notice_key, confirmation);
      this.view = {
        ...this.view,
        error: null,
        snapshot: {
          ...snapshot,
          state_revision: confirmation.state_revision,
          selected_entries: snapshot.selected_entries.filter(e => !confirmation.acknowledged || e.notice_key !== change.notice_key),
          entries: snapshot.entries.map((e) =>
            e.notice_key === change.notice_key
              ? {
                  ...e,
                  acknowledged: confirmation.acknowledged,
                  selected: confirmation.acknowledged ? false : e.selected,
                  attention_order: confirmation.attention_order,
                }
              : e
          ),
        },
      };
      this.publish();
      return confirmation;
    } catch (error) {
      conflict = error instanceof RouteSigmetHttpError && error.status === 409;
      throw error;
    } finally {
      clearTimeout(deadline);
      if (this.writeOwner === owner) this.writeOwner = null;
      owner.abort();
      this.writing = false;
      if (conflict && this.active()) await this.refresh();
      else if (this.active()) this.publish();
    }
  }
  dispose() {
    this.cancel();
    this.release();
    this.confirmed.clear();
    this.unobserve?.();
    this.unobserve = null;
    this.observer?.destroy();
    this.observer = null;
    this.client.removeQueries({ queryKey: routeSigmetsKey, exact: true });
    if (typeof document !== 'undefined')
      document.removeEventListener('visibilitychange', this.environment);
    if (typeof window !== 'undefined') {
      window.removeEventListener('online', this.environment);
      window.removeEventListener('offline', this.environment);
    }
    this.listeners.clear();
    this.view = empty();
  }
}
const sources = new WeakMap<QueryClient, RouteSigmetSource>();
export function getRouteSigmetSource(client: QueryClient) {
  let source = sources.get(client);
  if (!source) {
    source = new RouteSigmetSource(client);
    sources.set(client, source);
  }
  return source;
}
