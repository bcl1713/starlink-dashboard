import { describe, expect, it } from 'vitest';
import { parseOverviewDisplayMessage } from './overview-display-protocol';

const common = { v: 1, sender: 'display-a', target: null, seq: 1 };
const presence = {
  ...common,
  type: 'presence',
  label: 'Overview play-a',
  fullscreen: false,
  actions: ['recenter', 'fullscreen'],
};
const command = {
  ...common,
  type: 'command',
  target: 'display-b',
  requestId: 'request-a',
  action: 'recenter',
  expiresAtMs: 3000,
};
const result = {
  ...command,
  type: 'result',
  status: 'accepted',
  fullscreen: true,
};
delete (result as Partial<typeof command>).expiresAtMs;

describe('parseOverviewDisplayMessage', () => {
  it.each([
    { ...common, type: 'discover' },
    presence,
    { ...presence, target: 'controller-a', actions: [] },
    { ...common, type: 'bye' },
    command,
    { ...command, action: 'fullscreen', expiresAtMs: 0 },
    ...[
      'accepted',
      'interaction-required',
      'unsupported',
      'expired',
      'failed',
    ].map((status) => ({ ...result, status })),
  ])('accepts a closed valid message: $type $status', (message) => {
    expect(parseOverviewDisplayMessage(message)).toEqual(message);
  });

  // Dropping any validation below would admit non-protocol remote input.
  it.each([
    null,
    [],
    'presence',
    1,
    { ...presence, v: 2 },
    { ...presence, type: 'execute' },
    { ...presence, sender: '' },
    { ...presence, sender: '  ' },
    { ...presence, sender: 'x'.repeat(129) },
    { ...presence, target: '' },
    { ...presence, target: 42 },
    ...[0, -1, 1.5, Infinity, NaN, Number.MAX_SAFE_INTEGER + 1].map((seq) => ({
      ...presence,
      seq,
    })),
    { ...presence, label: '' },
    { ...presence, label: 'x'.repeat(129) },
    { ...presence, fullscreen: 'false' },
    { ...presence, actions: 'recenter' },
    { ...presence, actions: ['recenter', 'recenter'] },
    { ...presence, actions: ['recenter', 'reload'] },
    { ...presence, actions: new Array(1) },
    { ...presence, payload: 'arbitrary code' },
    { ...presence, [Symbol('extra')]: true },
    { ...common, type: 'discover', target: 'someone' },
    { ...common, type: 'bye', target: 'someone' },
    { ...command, target: null },
    { ...command, requestId: '' },
    { ...command, requestId: 'x'.repeat(129) },
    { ...command, action: 'reload' },
    ...[-1, Infinity, NaN, '3000'].map((expiresAtMs) => ({
      ...command,
      expiresAtMs,
    })),
    { ...result, target: null },
    { ...result, status: 'timeout' },
    { ...result, fullscreen: 1 },
  ])('rejects malformed, oversized or unknown input %#', (message) => {
    expect(parseOverviewDisplayMessage(message)).toBeNull();
  });

  it('rejects missing and inherited fields without evaluating accessors', () => {
    for (const key of Object.keys(presence)) {
      const missing: Record<string, unknown> = { ...presence };
      delete missing[key];
      expect(parseOverviewDisplayMessage(missing)).toBeNull();
      expect(
        parseOverviewDisplayMessage(
          Object.assign(
            Object.create({ [key]: presence[key as keyof typeof presence] }),
            missing
          )
        )
      ).toBeNull();
    }
    const getter = { ...presence };
    Object.defineProperty(getter, 'label', {
      get: () => {
        throw new Error('must not evaluate');
      },
    });
    expect(parseOverviewDisplayMessage(getter)).toBeNull();
  });

  it('rejects inherited, accessor and extra capability fields without evaluating them', () => {
    const inherited = new Array(1);
    Object.setPrototypeOf(
      inherited,
      Object.assign(Object.create(Array.prototype), { 0: 'recenter' })
    );
    expect(
      parseOverviewDisplayMessage({ ...presence, actions: inherited })
    ).toBeNull();
  });

  it('rejects capability accessors without evaluating them', () => {
    const getter = ['recenter'];
    let reads = 0;
    Object.defineProperty(getter, '0', {
      get: () => {
        reads++;
        return 'recenter';
      },
    });
    expect(
      parseOverviewDisplayMessage({ ...presence, actions: getter })
    ).toBeNull();
    expect(reads).toBe(0);
  });

  it('rejects extra capability payload fields', () => {
    expect(
      parseOverviewDisplayMessage({
        ...presence,
        actions: Object.assign(['recenter'], { payload: 'remote data' }),
      })
    ).toBeNull();
  });

  it('accepts boundary lengths and detaches the validated capabilities', () => {
    const input = {
      ...presence,
      sender: 'x'.repeat(128),
      label: 'y'.repeat(128),
      seq: Number.MAX_SAFE_INTEGER,
    };
    const parsed = parseOverviewDisplayMessage(input);
    expect(parsed).toEqual(input);
    input.actions.push('reload');
    expect(parsed?.type === 'presence' && parsed.actions).toEqual([
      'recenter',
      'fullscreen',
    ]);
  });
});
