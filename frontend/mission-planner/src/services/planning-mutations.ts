import type { QueryClient } from '@tanstack/react-query';
import { rememberMission } from './mission-cache';
import type { PlanningEvaluation, PlanningView } from '../types/planning';

/** One durable write queue per mission. A failed CAS is never retried. */
export class PlanningMissionController {
  private tail: Promise<unknown> = Promise.resolve();
  private sequence = 0;
  private previews = new Map<
    string,
    { token: string; base: string | undefined }
  >();
  private edits = new Map<string, Set<symbol>>();
  private editVersion = 0;
  private editVersions = new Map<string, number>();
  localEditIdentity(ids: string[]) {
    return ids.map((id) => `${id}:${this.editVersions.get(id) ?? 0}`).join('|');
  }
  private editListeners = new Set<() => void>();
  subscribeEdits = (listener: () => void) => {
    this.editListeners.add(listener);
    return () => {
      this.editListeners.delete(listener);
    };
  };
  editSnapshot = () => this.editVersion;
  setLocalEdits(legId: string, owner: symbol, dirty: boolean) {
    const owners = this.edits.get(legId) ?? new Set<symbol>();
    const changed = dirty || owners.has(owner);
    if (dirty) owners.add(owner);
    else owners.delete(owner);
    if (owners.size) this.edits.set(legId, owners);
    else this.edits.delete(legId);
    if (changed) {
      this.editVersion++;
      this.editVersions.set(legId, (this.editVersions.get(legId) ?? 0) + 1);
      for (const listener of this.editListeners) listener();
    }
  }
  hasLocalEdits(ids: string[]) {
    return ids.some((id) => this.edits.has(id));
  }
  requireSavedSources(ids: string[]) {
    if (this.hasLocalEdits(ids))
      throw new Error(
        'Save or resolve source edits before planning or publication'
      );
  }
  private owners = 0;
  private pending = 0;
  private client: QueryClient;
  readonly missionId: string;
  private retire: () => void;
  constructor(client: QueryClient, missionId: string, retire: () => void) {
    this.client = client;
    this.missionId = missionId;
    this.retire = retire;
  }
  currentView(): PlanningView | null {
    return (
      this.client.getQueryData<PlanningView>(['planning', this.missionId]) ??
      null
    );
  }
  retain() {
    this.owners++;
  }
  release() {
    this.owners--;
    this.maybeRetire();
  }
  private maybeRetire() {
    queueMicrotask(() => {
      if (this.owners === 0 && this.pending === 0) this.retire();
    });
  }
  enqueueMutation<T>(
    operation: (view: PlanningView) => Promise<T>,
    committedView: (result: T) => PlanningView | null
  ): Promise<T> {
    this.pending++;
    const result = this.tail.then(async () => {
      const current = this.currentView();
      if (!current)
        throw new Error('Planning view must be loaded before saving');
      const value = await operation(current);
      const saved = committedView(value);
      if (saved && saved.revision >= (this.currentView()?.revision ?? 0)) {
        this.client.setQueryData(['planning', this.missionId], saved);
        rememberMission(this.client, saved.mission);
        void this.client.invalidateQueries({ queryKey: ['missions'] });
      }
      return value;
    });
    this.tail = result.catch(() => undefined);
    return result.finally(() => {
      this.pending--;
      this.maybeRetire();
    });
  }
  beginPreview(legId: string, inputIdentity: string): string {
    const token = `${++this.sequence}:${inputIdentity}`;
    this.previews.set(legId, {
      token,
      base: this.currentView()?.expected_legs.find(
        (card) => card.leg.id === legId
      )?.input_identity,
    });
    return token;
  }
  acceptPreview(token: string, result: PlanningEvaluation): boolean {
    // The request token binds the response to a local draft; evaluation input
    // identities describe derived geometry and differ from card identities.
    void result;
    for (const [legId, preview] of this.previews) {
      if (preview.token === token)
        return (
          preview.base ===
          this.currentView()?.expected_legs.find(
            (card) => card.leg.id === legId
          )?.input_identity
        );
    }
    return false;
  }
  cancelPreview(legId: string) {
    this.previews.delete(legId);
  }
}

const controllers = new WeakMap<
  QueryClient,
  Map<string, PlanningMissionController>
>();
export function planningMissionController(
  client: QueryClient,
  missionId: string
) {
  let missions = controllers.get(client);
  if (!missions) {
    missions = new Map();
    controllers.set(client, missions);
  }
  let controller = missions.get(missionId);
  if (!controller) {
    controller = new PlanningMissionController(client, missionId, () => {
      if (missions!.get(missionId) === controller) missions!.delete(missionId);
    });
    missions.set(missionId, controller);
  }
  return controller;
}
export function currentLeg(
  view: PlanningView,
  legId: string,
  identity?: string
) {
  const card = view.expected_legs.find((card) => card.leg.id === legId);
  if (!card || (identity && card.input_identity !== identity))
    throw Object.assign(new Error('Planning inputs changed'), {
      response: { status: 409 },
    });
  return card;
}
