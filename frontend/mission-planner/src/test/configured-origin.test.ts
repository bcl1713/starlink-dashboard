import { describe, expect, it } from 'vitest';
import {
  configuredOrigin,
  requestUrlPattern,
  routeGlob,
  routeUrl,
} from '../../tests/e2e/support/configured-origin';

describe('configured E2E origin helpers', () => {
  it('builds route and request patterns from a supplied non-default port', () => {
    const baseURL = 'http://localhost:5187/';

    expect(configuredOrigin(baseURL)).toBe('http://localhost:5187');
    expect(routeGlob(baseURL, '/api/v2/missions')).toBe(
      'http://localhost:5187/api/v2/missions**'
    );
    expect(routeUrl(baseURL, '/api/routes')).toBe(
      'http://localhost:5187/api/routes'
    );
    expect('http://localhost:5187/api/v2/missions?limit=10').toMatch(
      requestUrlPattern(baseURL, '/api/v2/missions')
    );
    expect('http://localhost:5187/api/v2/missions').toMatch(
      requestUrlPattern(baseURL, '/api/v2/missions')
    );
    expect(routeGlob('http://localhost:5173', '/api/routes')).toBe(
      'http://localhost:5173/api/routes**'
    );
  });

  it('rejects a missing base URL and a relative route path', () => {
    expect(() => configuredOrigin(undefined)).toThrow(/baseURL/i);
    expect(() => routeGlob('http://localhost:5173', 'api/routes')).toThrow(
      /pathname/i
    );
  });
});
