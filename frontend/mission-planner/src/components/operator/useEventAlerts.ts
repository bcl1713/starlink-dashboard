import { useEffect, useRef, useState } from 'react';
import type { OperatorEventsState } from '@/hooks/api/useOperatorEvents';
import { selectAlertBatch, eventAlertKey } from './eventAlerts';
import type { AlertBatch } from './eventAlerts';
import { createEventEmitter } from './eventEmitter';
import type { AlertPreferences, DeliveryResult } from './eventEmitter';
const defaultPreferences: AlertPreferences = {
  enabled: true,
  sound: true,
  vibration: true,
};
function loadPreferences(): AlertPreferences {
  try {
    const value = JSON.parse(
      localStorage.getItem('operator-alert-preferences') ?? 'null'
    );
    if (
      value &&
      typeof value.enabled === 'boolean' &&
      typeof value.sound === 'boolean' &&
      typeof value.vibration === 'boolean'
    )
      return value;
  } catch {
    /* Settings remain usable for this session. */
  }
  return defaultPreferences;
}
export function useEventAlerts(events: OperatorEventsState) {
  const [preferences, setPreferences] = useState(loadPreferences);
  const [batch, setBatch] = useState<AlertBatch | null>(null);
  const [delivery, setDelivery] = useState<DeliveryResult | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const latest = useRef({ events, preferences });
  latest.current = { events, preferences };
  const emitter = useRef<ReturnType<typeof createEventEmitter> | null>(null);
  const catchUp = useRef(true);
  const coordinationUnavailable = useRef(false);
  const scope = events.snapshot
    ? JSON.stringify([
        events.snapshot.store_id,
        events.snapshot.source_mode,
        events.snapshot.simulation_run_id,
        events.snapshot.mission_id,
      ])
    : '';
  useEffect(() => {
    if (events.visible && preferences.enabled && !events.failed)
      catchUp.current = true;
  }, [events.visible, preferences.enabled, events.failed]);
  useEffect(() => {
    setBatch(null);
    setDelivery(null);
    if (!scope) return;
    const storageKey = `operator-alert-emissions:${scope}`;
    const emitted = new Map<string, number>();
    try {
      const stored = JSON.parse(localStorage.getItem(storageKey) ?? '[]');
      if (Array.isArray(stored))
        for (const item of stored) {
          if (
            Array.isArray(item) &&
            typeof item[0] === 'string' &&
            typeof item[1] === 'number' &&
            item[1] > Date.now() - 7 * 86400000
          )
            emitted.set(item[0], item[1]);
        }
    } catch {
      setWarning(
        'Cue history is session-only. Shared acknowledgment is unchanged.'
      );
    }
    let closed = false,
      busy = false,
      hasCandidates = false;
    coordinationUnavailable.current = false;
    let lastCue = -Infinity,
      coalescingStarted = performance.now();
    catchUp.current = true;
    const output = createEventEmitter({
      preferences: () => latest.current.preferences,
      onVisual: (value) => {
        if (!closed) setBatch(value);
      },
    });
    emitter.current = output;
    setDelivery(output.status());
    async function evaluate() {
      const current = latest.current;
      if (
        closed ||
        busy ||
        coordinationUnavailable.current ||
        !current.events.snapshot ||
        current.events.failed ||
        current.events.blocked
      )
        return;
      const now = performance.now();
      const hasUnseen = current.events.snapshot.events.some(
        (event) =>
          event.active &&
          event.notification.eligible &&
          !emitted.has(eventAlertKey(current.events.snapshot!, event))
      );
      if (!hasUnseen) {
        hasCandidates = false;
        return;
      }
      if (!hasCandidates) {
        coalescingStarted = now;
        hasCandidates = true;
      }
      const selected = selectAlertBatch({
        snapshot: current.events.snapshot,
        receivedAt: current.events.receivedAt,
        now,
        lastCueAt: lastCue,
        emitted: new Set(emitted.keys()),
        visible: current.events.visible,
        enabled: current.preferences.enabled,
        catchUp: catchUp.current,
        coalescingStartedAt: coalescingStarted,
      });
      if (!selected) return;
      busy = true;
      try {
        const result = await output.emit(selected);
        if (closed) return;
        setDelivery(result);
        if (result.coordination === 'unavailable') {
          coordinationUnavailable.current = true;
          return;
        }
        // Local reservations suppress attempts; they never mean acknowledgment
        // or guaranteed physical sound/vibration delivery.
        for (const key of selected.keys) emitted.set(key, Date.now());
        while (emitted.size > 2000)
          emitted.delete(emitted.keys().next().value!);
        try {
          localStorage.setItem(storageKey, JSON.stringify([...emitted]));
        } catch {
          setWarning('Cue history is session-only. Keep this page open.');
        }
        if (result.visual) lastCue = performance.now();
        catchUp.current = false;
        hasCandidates = false;
        coalescingStarted = performance.now();
      } finally {
        busy = false;
      }
    }
    void evaluate();
    const timer = setInterval(() => {
      void evaluate();
    }, 1000);
    return () => {
      closed = true;
      clearInterval(timer);
      output.dispose();
      if (emitter.current === output) emitter.current = null;
    };
  }, [scope]);
  function updatePreferences(value: AlertPreferences) {
    latest.current.preferences = value;
    setPreferences(value);
    if (value.enabled) catchUp.current = true;
    try {
      localStorage.setItem('operator-alert-preferences', JSON.stringify(value));
    } catch {
      setWarning('Alert preferences are session-only.');
    }
  }
  async function enableOutput() {
    coordinationUnavailable.current = false;
    const value = await emitter.current?.enable();
    if (value) setDelivery(value);
  }
  return {
    preferences,
    updatePreferences,
    batch,
    delivery,
    warning,
    enableOutput,
  };
}
export type EventAlertsState = ReturnType<typeof useEventAlerts>;
