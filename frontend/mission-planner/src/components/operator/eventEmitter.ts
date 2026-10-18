import type { AlertBatch } from './eventAlerts';
import { reserveEventCues } from './eventDeliveryLock';
export interface AlertPreferences {
  enabled: boolean;
  sound: boolean;
  vibration: boolean;
}
export interface DeliveryResult {
  visual: boolean;
  sound: 'enabled' | 'needs_interaction' | 'muted' | 'unavailable';
  vibration: 'enabled' | 'needs_interaction' | 'muted' | 'unavailable';
  coordination: 'ready' | 'unavailable';
}
interface EmitterOptions {
  preferences: () => AlertPreferences;
  onVisual: (batch: AlertBatch) => void;
  claim?: (keys: string[]) => Promise<string[]>;
}
export function createEventEmitter(options: EmitterOptions) {
  let disposed = false,
    unlocked = false;
  let audio: AudioContext | undefined;
  const oscillators = new Set<OscillatorNode>();
  const owner = crypto.randomUUID();
  const claim =
    options.claim ?? ((keys: string[]) => reserveEventCues(keys, owner));
  function status(): DeliveryResult {
    const preferences = options.preferences();
    return {
      visual: false,
      coordination: 'ready',
      sound: !preferences.sound
        ? 'muted'
        : !globalThis.AudioContext
          ? 'unavailable'
          : audio?.state === 'running'
            ? 'enabled'
            : 'needs_interaction',
      vibration: !preferences.vibration
        ? 'muted'
        : typeof navigator.vibrate !== 'function'
          ? 'unavailable'
          : unlocked
            ? 'enabled'
            : 'needs_interaction',
    };
  }
  async function enable() {
    if (disposed) return status();
    unlocked = true;
    if (options.preferences().sound && globalThis.AudioContext) {
      try {
        audio ??= new AudioContext();
        await audio.resume();
      } catch {
        /* The status remains honest about suspended/unsupported audio. */
      }
    }
    return status();
  }
  async function emit(batch: AlertBatch): Promise<DeliveryResult> {
    const result = status();
    if (disposed || !options.preferences().enabled) return result;
    let reserved: string[];
    try {
      if (navigator.locks) {
        reserved = await navigator.locks.request(
          'operator-event-cue',
          { ifAvailable: true },
          (lock) => (lock ? claim(batch.keys) : Promise.resolve([]))
        );
      } else reserved = await claim(batch.keys);
    } catch {
      return { ...result, coordination: 'unavailable' };
    }
    if (disposed || !options.preferences().enabled) return result;
    const allowed = new Set(reserved);
    const events = batch.events.filter((_, index) =>
      allowed.has(batch.keys[index])
    );
    if (!events.length) return result;
    options.onVisual({ ...batch, events, keys: reserved });
    result.visual = true;
    const preferences = options.preferences();
    const audible =
      batch.audible && events.some((e) => e.kind !== 'issue_followup');
    if (!audible) result.sound = 'muted';
    if (
      audible &&
      preferences.sound &&
      unlocked &&
      audio?.state === 'running'
    ) {
      try {
        const oscillator = audio.createOscillator(),
          gain = audio.createGain();
        oscillator.frequency.value = 660;
        gain.gain.value = 0.04;
        oscillator.connect(gain);
        gain.connect(audio.destination);
        oscillators.add(oscillator);
        oscillator.onended = () => {
          oscillators.delete(oscillator);
          oscillator.disconnect();
          gain.disconnect();
        };
        oscillator.start();
        oscillator.stop(audio.currentTime + 0.12);
        result.sound = 'enabled';
      } catch {
        result.sound = 'unavailable';
      }
    }
    if (
      preferences.vibration &&
      unlocked &&
      typeof navigator.vibrate === 'function'
    ) {
      try {
        result.vibration = navigator.vibrate(200) ? 'enabled' : 'unavailable';
      } catch {
        result.vibration = 'unavailable';
      }
    }
    return result;
  }
  function dispose() {
    disposed = true;
    for (const oscillator of oscillators) {
      try {
        oscillator.stop();
      } catch {
        /* Already ended. */
      }
    }
    oscillators.clear();
    if (audio) void audio.close().catch(() => {});
  }
  return { emit, enable, status, dispose };
}
