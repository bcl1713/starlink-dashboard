/** @vitest-environment jsdom */
import { afterEach, expect, it, vi } from 'vitest';
import { createEventEmitter } from './eventEmitter';
import { eventFixture } from '@/test/operator-event-fixtures';
const batch = {
  events: [eventFixture()],
  remaining: 0,
  keys: ['occurrence'],
  audible: true,
};
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
it('never starts audio or vibration on load or before user interaction', async () => {
  const vibrate = vi.fn(() => true);
  vi.stubGlobal('navigator', { vibrate });
  const visual = vi.fn();
  const emitter = createEventEmitter({
    preferences: () => ({ enabled: true, sound: true, vibration: true }),
    onVisual: visual,
    claim: async (keys) => keys,
  });
  expect(vibrate).not.toHaveBeenCalled();
  const result = await emitter.emit(batch);
  expect(visual).toHaveBeenCalledOnce();
  expect(vibrate).not.toHaveBeenCalled();
  expect(result.vibration).toBe('needs_interaction');
  emitter.dispose();
});
it('keeps routine follow-up silent, reports unsupported output and stops after disposal', async () => {
  const visual = vi.fn();
  const emitter = createEventEmitter({
    preferences: () => ({ enabled: true, sound: true, vibration: true }),
    onVisual: visual,
    claim: async (keys) => keys,
  });
  await emitter.enable();
  const result = await emitter.emit({ ...batch, audible: false });
  expect(result.sound).toBe('muted');
  emitter.dispose();
  await emitter.emit(batch);
  expect(visual).toHaveBeenCalledOnce();
});
it('does not claim delivery without coordination or emit already reserved occurrences', async () => {
  const visual = vi.fn();
  const emitter = createEventEmitter({
    preferences: () => ({ enabled: true, sound: false, vibration: false }),
    onVisual: visual,
    claim: async () => [],
  });
  expect((await emitter.emit(batch)).visual).toBe(false);
  expect(visual).not.toHaveBeenCalled();
  emitter.dispose();
  const unavailable = createEventEmitter({
    preferences: () => ({ enabled: true, sound: true, vibration: true }),
    onVisual: visual,
    claim: async () => {
      throw new Error('Storage unavailable');
    },
  });
  expect((await unavailable.emit(batch)).coordination).toBe('unavailable');
  expect(visual).not.toHaveBeenCalled();
  unavailable.dispose();
});
