import { describe, expect, it } from 'vitest';
import {
  newTransportDraft,
  toTransportCommand,
  replaceApplication,
} from './transportForms';

describe('transport form contracts', () => {
  it('saves applied-only without intent, request, check or invented time', () => {
    const draft = newTransportDraft('synthetic-mission-a');
    draft.input.payload.services[0].service = 'IPTV';
    draft.input.payload.services[0].applied = {
      transport: 'Ka',
      time: { at: null, precision: 'unknown' },
    };
    const command = toTransportCommand(draft);
    expect(command.operation).toBe('create');
    expect(command.body).toMatchObject({
      payload: {
        services: [
          {
            intended: null,
            requested: null,
            checked: null,
            applied: { transport: 'Ka', time: { at: null } },
          },
        ],
      },
    });
  });
  it('allows independent checked-only entry and limits generated title', () => {
    const draft = newTransportDraft('synthetic-mission-a');
    const first = draft.input.payload.services[0];
    first.service = 'VTC';
    first.checked = {
      result: 'satisfactory',
      time: { at: null, precision: 'unknown' },
      note: '',
    };
    expect(toTransportCommand(draft).body.payload.title).toBe('VTC');
    draft.input.payload.services = Array.from({ length: 32 }, () => ({
      ...first,
      row_id: crypto.randomUUID(),
      service: 'V'.repeat(200),
    }));
    expect(
      toTransportCommand(draft).body.payload.title.length
    ).toBeLessThanOrEqual(200);
  });
  it('clears an old check when application changes but preserves row identity', () => {
    const draft = newTransportDraft('synthetic-mission-a');
    const first = draft.input.payload.services[0];
    first.checked = {
      result: 'satisfactory',
      time: { at: null, precision: 'unknown' },
      note: '',
    };
    const changed = replaceApplication(first, {
      transport: 'X',
      time: { at: null, precision: 'unknown' },
    });
    expect(changed.checked).toBeNull();
    expect(changed.row_id).toBe(first.row_id);
  });
  it('rejects blank labels and reversed or malformed planned times', () => {
    const draft = newTransportDraft('synthetic-mission-a');
    expect(() => toTransportCommand(draft)).toThrow('Service');
    draft.input.payload.services[0].service = 'VTC';
    draft.input.time.planned_start_at = 'not-a-time';
    expect(() => toTransportCommand(draft)).toThrow('UTC');
    draft.input.time.planned_start_at = '2026-10-17T18:00:00Z';
    draft.input.time.planned_end_at = '2026-10-17T17:00:00Z';
    expect(() => toTransportCommand(draft)).toThrow('end');
  });
});

it('creates stable row IDs on ordinary LAN HTTP without randomUUID', () => {
  const old = globalThis.crypto;
  Object.defineProperty(globalThis, 'crypto', {
    configurable: true,
    value: { getRandomValues: old.getRandomValues.bind(old) },
  });
  try {
    expect(
      newTransportDraft('synthetic-a').input.payload.services[0].row_id
    ).toMatch(/^[0-9a-f-]{36}$/);
  } finally {
    Object.defineProperty(globalThis, 'crypto', {
      configurable: true,
      value: old,
    });
  }
});
