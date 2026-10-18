import type { EventSnapshot, OperationalEvent } from '@/types/operatorEvents';

export function nextRequirement(
  snapshot?: EventSnapshot
): OperationalEvent | undefined {
  const now = Date.parse(snapshot?.as_of ?? '');
  return snapshot?.events
    .filter(
      (event) =>
        event.active &&
        event.kind === 'call_start' &&
        event.state === 'upcoming' &&
        Number.isFinite(Date.parse(event.due_at ?? '')) &&
        Date.parse(event.due_at!) >= now
    )
    .sort((a, b) => Date.parse(a.due_at!) - Date.parse(b.due_at!))[0];
}
