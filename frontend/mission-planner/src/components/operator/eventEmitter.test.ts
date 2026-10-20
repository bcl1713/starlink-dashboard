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
it('constructs and emits on aircraft HTTP without the secure randomUUID API', async () => {
  vi.stubGlobal('crypto', {
    getRandomValues: (bytes: Uint8Array) => bytes.fill(7),
  });
  const visual = vi.fn();
  const emitter = createEventEmitter({
    preferences: () => ({ enabled: true, sound: false, vibration: false }),
    onVisual: visual,
    claim: async (keys) => keys,
  });
  expect((await emitter.emit(batch)).visual).toBe(true);
  emitter.dispose();
});

it('reports rejected audio permission and unavailable vibration without claiming delivery', async () => {
  class BlockedAudio {
    state = 'suspended';
    resume = vi.fn(async () => {
      throw new Error('gesture denied');
    });
    close = vi.fn(async () => {});
  }
  vi.stubGlobal('AudioContext', BlockedAudio);
  vi.stubGlobal('navigator', { vibrate: () => false });
  const emitter = createEventEmitter({
    preferences: () => ({ enabled: true, sound: true, vibration: true }),
    onVisual: vi.fn(),
    claim: async (keys) => keys,
  });
  expect((await emitter.enable()).sound).toBe('needs_interaction');
  const result = await emitter.emit(batch);
  expect(result).toMatchObject({
    visual: true,
    sound: 'needs_interaction',
    vibration: 'unavailable',
  });
  emitter.dispose();
});

it('requests one sound and vibration only after explicit enable and honors subsequent mute', async () => {
  const oscillator = {
    frequency: { value: 0 },
    connect: vi.fn(),
    disconnect: vi.fn(),
    start: vi.fn(),
    stop: vi.fn(),
    onended: null as (() => void) | null,
  };
  const gain = { gain: { value: 0 }, connect: vi.fn(), disconnect: vi.fn() };
  const close = vi.fn(async () => {});
  class Audio {
    state = 'running';
    currentTime = 0;
    destination = {};
    resume = vi.fn(async () => {});
    createOscillator = () => oscillator;
    createGain = () => gain;
    close = close;
  }
  const vibrate = vi.fn(() => true);
  vi.stubGlobal('AudioContext', Audio);
  vi.stubGlobal('navigator', { vibrate });
  const preferences = { enabled: true, sound: true, vibration: true };
  const visual = vi.fn();
  const emitter = createEventEmitter({
    preferences: () => preferences,
    onVisual: visual,
    claim: async (keys) => keys,
  });
  expect(oscillator.start).not.toHaveBeenCalled();
  expect(vibrate).not.toHaveBeenCalled();
  await emitter.enable();
  expect(await emitter.emit(batch)).toMatchObject({
    visual: true,
    sound: 'enabled',
    vibration: 'enabled',
  });
  expect(oscillator.start).toHaveBeenCalledOnce();
  expect(oscillator.stop).toHaveBeenCalledExactlyOnceWith(0.12);
  expect(vibrate).toHaveBeenCalledExactlyOnceWith(200);
  preferences.enabled = false;
  await emitter.emit(batch);
  expect(visual).toHaveBeenCalledOnce();
  expect(oscillator.start).toHaveBeenCalledOnce();
  expect(vibrate).toHaveBeenCalledOnce();
  oscillator.onended?.();
  emitter.dispose();
  expect(close).toHaveBeenCalledOnce();
});
