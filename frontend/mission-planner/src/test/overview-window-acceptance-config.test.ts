import { afterEach, describe, expect, it, vi } from 'vitest';
import ordinary from '../../playwright.config';

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});
describe('production window acceptance isolation', () => {
  it.each([
    undefined,
    'https://127.0.0.1:15257',
    'http://example.com',
    'http://user:pass@localhost:15257',
    'http://localhost:15257/api',
  ])('rejects unsafe base URL %s', async (url) => {
    vi.stubEnv('OVERVIEW_ACCEPTANCE_BASE_URL', url);
    await expect(
      import('../../playwright.window-acceptance.config')
    ).rejects.toThrow('loopback HTTP');
  });
  it.each([
    'http://127.0.0.1:15257',
    'http://localhost:15257',
    'http://[::1]:15257',
  ])('runs only production against %s without a preview', async (url) => {
    vi.stubEnv('OVERVIEW_ACCEPTANCE_BASE_URL', url);
    const { default: config } = await import(
      '../../playwright.window-acceptance.config'
    );
    expect(config.use?.baseURL).toBe(url);
    expect(config.webServer).toBeUndefined();
    expect(config.workers).toBe(1);
    expect(config.retries).toBe(0);
    expect(config.testMatch).toBe('overview-window-production.spec.ts');
    expect(ordinary.testIgnore).toContain(
      '**/overview-window-production.spec.ts'
    );
  });
});
