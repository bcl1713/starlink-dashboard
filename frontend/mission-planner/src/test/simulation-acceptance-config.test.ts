import { afterEach, expect, it, vi } from 'vitest';
afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});
it.each([
  'https://127.0.0.1:15262',
  'http://example.com',
  'http://user:pass@127.0.0.1',
  'http://127.0.0.1/path',
  'http://127.0.0.1/?q=1',
  'http://127.0.0.1/#hash',
  '',
])('rejects unsafe acceptance origin %s', async (origin) => {
  vi.stubEnv('SIMULATION_ACCEPTANCE_BASE_URL', origin);
  await expect(
    import('../../playwright.simulation-acceptance.config')
  ).rejects.toThrow('loopback HTTP origin');
});
it('selects real production journeys with bounded timeout and no Vite server', async () => {
  vi.stubEnv('SIMULATION_ACCEPTANCE_BASE_URL', 'http://127.0.0.1:15262');
  const config = (await import('../../playwright.simulation-acceptance.config'))
    .default;
  expect(config.testMatch).toBe('simulation-run-production.spec.ts');
  expect(config.timeout).toBe(240000);
  expect(config.workers).toBe(1);
  expect(config.retries).toBe(0);
  expect(config.webServer).toBeUndefined();
  expect(config.use?.baseURL).toBe('http://127.0.0.1:15262');
  expect(config.use?.video).toEqual({
    mode: 'on',
    size: { width: 1920, height: 1080 },
  });
  expect(config.use?.launchOptions?.args).toContain('--window-size=1920,1080');
});
