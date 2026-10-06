import { afterEach, describe, expect, it, vi } from 'vitest';
import ordinary from '../../playwright.config';

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});
describe('production weather acceptance isolation', () => {
  it('selects only the isolated source-comparison spec', async () => {
    vi.stubEnv('WEATHER_ACCEPTANCE_BASE_URL', 'http://127.0.0.1:15288');
    vi.stubEnv('WEATHER_ACCEPTANCE_MODE', 'comparison');
    const { default: config } = await import(
      '../../playwright.weather-acceptance.config'
    );
    expect(config.testMatch).toBe('overview-weather-comparison.spec.ts');
    expect(config.webServer).toBeUndefined();
    expect(ordinary.testIgnore).toContain(
      '**/overview-weather-comparison.spec.ts'
    );
  });
  it.each([
    undefined,
    'https://127.0.0.1:15278',
    'http://example.com',
    'http://user:pass@localhost:15278',
    'http://localhost:15278/api',
  ])('rejects unsafe base URL %s', async (url) => {
    vi.stubEnv('WEATHER_ACCEPTANCE_BASE_URL', url);
    await expect(
      import('../../playwright.weather-acceptance.config')
    ).rejects.toThrow('loopback HTTP');
  });
  it.each([
    'http://127.0.0.1:15278',
    'http://localhost:15278',
    'http://[::1]:15278',
  ])('runs only production against %s without a preview', async (url) => {
    vi.stubEnv('WEATHER_ACCEPTANCE_BASE_URL', url);
    const { default: config } = await import(
      '../../playwright.weather-acceptance.config'
    );
    expect(config.use?.baseURL).toBe(url);
    expect(config.webServer).toBeUndefined();
    expect(config.workers).toBe(1);
    expect(config.retries).toBe(0);
    expect(config.testMatch).toBe('overview-weather-production.spec.ts');
    expect(ordinary.testIgnore).toContain(
      '**/overview-weather-production.spec.ts'
    );
  });
});
