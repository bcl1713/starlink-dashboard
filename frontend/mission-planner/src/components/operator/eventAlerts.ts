import type { EventSnapshot, OperationalEvent } from '@/types/operatorEvents';
export interface AlertBatch {
  events: OperationalEvent[];
  remaining: number;
  keys: string[];
  audible: boolean;
}
export interface AlertSelectionInput {
  snapshot: EventSnapshot;
  now: number;
  receivedAt: number;
  lastCueAt: number;
  emitted: ReadonlySet<string>;
  visible: boolean;
  enabled: boolean;
  catchUp: boolean;
  coalescingStartedAt: number;
}
export function eventAlertKey(
  snapshot: EventSnapshot,
  event: OperationalEvent
): string {
  return JSON.stringify([
    snapshot.store_id,
    snapshot.source_mode,
    snapshot.simulation_run_id,
    snapshot.mission_id,
    event.notification.generation,
    event.notification.severity_generation,
  ]);
}
export function selectAlertBatch(
  input: AlertSelectionInput
): AlertBatch | null {
  const { snapshot, now, receivedAt } = input;
  if (
    !input.enabled ||
    !input.visible ||
    snapshot.truncated ||
    now < receivedAt ||
    now - receivedAt > 30000 ||
    now - input.lastCueAt < 30000 ||
    (!input.catchUp && now - input.coalescingStartedAt < 5000)
  )
    return null;
  const candidates = snapshot.events
    .filter(
      (e) =>
        e.active &&
        e.freshness === 'fresh' &&
        e.notification.eligible &&
        !e.notification.retired &&
        !e.notification.acknowledged &&
        e.notification.generation &&
        !input.emitted.has(eventAlertKey(snapshot, e))
    )
    .sort(
      (a, b) =>
        a.notification.priority - b.notification.priority ||
        Date.parse(a.due_at ?? '') - Date.parse(b.due_at ?? '') ||
        a.event_id.localeCompare(b.event_id)
    );
  if (!candidates.length) return null;
  return {
    events: candidates.slice(0, 3),
    remaining: Math.max(0, candidates.length - 3),
    keys: candidates.map((e) => eventAlertKey(snapshot, e)),
    audible: candidates.slice(0, 3).some((e) => e.kind !== 'issue_followup'),
  };
}
