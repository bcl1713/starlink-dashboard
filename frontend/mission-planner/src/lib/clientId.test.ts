import { afterEach, describe, expect, it, vi } from 'vitest';
import { createClientId } from './clientId';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('createClientId', () => {
  it('uses crypto.randomUUID when the browser supports it', () => {
    vi.stubGlobal('crypto', {
      randomUUID: () => 'secure-browser-id',
    });

    expect(createClientId()).toBe('secure-browser-id');
  });

  it('creates distinct client IDs when crypto.randomUUID is unavailable', () => {
    vi.stubGlobal('crypto', undefined);

    const ids = [createClientId(), createClientId()];

    expect(ids[0]).toMatch(/^client-/);
    expect(new Set(ids)).toHaveLength(2);
  });
});
