import { expect, it } from 'vitest';
import { selectAlertBatch } from './eventAlerts';
import { eventFixture, eventSnapshot } from '@/test/operator-event-fixtures';
const input = () => ({
  snapshot: eventSnapshot(),
  now: 1000,
  receivedAt: 1000,
  lastCueAt: -Infinity,
  emitted: new Set<string>(),
  visible: true,
  enabled: true,
  catchUp: true,
  coalescingStartedAt: 1000,
});
it('bounds catch-up to one three-item cue and consumes the remainder without acknowledging events', () => {
  const snapshot = eventSnapshot({
    events: Array.from({ length: 10 }, (_, i) =>
      eventFixture({
        event_id: `e-${i}`,
        notification: {
          ...eventFixture().notification,
          generation: `o-${i}`,
          priority: i === 9 ? 0 : 4,
        },
      })
    ),
  });
  const result = selectAlertBatch({ ...input(), snapshot });
  expect(result?.events).toHaveLength(3);
  expect(result?.keys).toHaveLength(10);
  expect(result?.remaining).toBe(7);
  expect(snapshot.events.every((e) => !e.notification.acknowledged)).toBe(true);
  expect(
    selectAlertBatch({ ...input(), snapshot, emitted: new Set(result?.keys) })
  ).toBeNull();
});
it('uses server eligibility, fresh snapshots, visible state and local cooldown only', () => {
  for (const patch of [
    { visible: false },
    { enabled: false },
    { now: 31001 },
    { lastCueAt: 0 },
  ])
    expect(selectAlertBatch({ ...input(), ...patch })).toBeNull();
  const event = eventFixture();
  event.notification.eligible = false;
  expect(
    selectAlertBatch({
      ...input(),
      snapshot: eventSnapshot({ events: [event] }),
    })
  ).toBeNull();
});
it('coalesces continuous crossings for five seconds and keeps routine follow-up silent', () => {
  expect(
    selectAlertBatch({ ...input(), catchUp: false, now: 5999 })
  ).toBeNull();
  const event = eventFixture({ kind: 'issue_followup' });
  expect(
    selectAlertBatch({
      ...input(),
      catchUp: false,
      now: 6000,
      snapshot: eventSnapshot({ events: [event] }),
    })?.audible
  ).toBe(false);
});
