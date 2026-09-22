import { describe, expect, it } from 'vitest';
import config from '../../playwright.config';

function oneWebServer() {
  if (!config.webServer || Array.isArray(config.webServer)) {
    throw new Error('Expected exactly one Playwright webServer configuration');
  }

  return config.webServer;
}

describe('Playwright harness policy', () => {
  it('uses explicit startup and browser-test budgets with no-retry diagnostics', () => {
    expect(oneWebServer()).toMatchObject({
      timeout: expect.any(Number),
    });
    expect(config.timeout).toBe(60_000);
    expect(config.use?.trace).toBe('retain-on-failure');
    expect(config.retries).toBe(0);
  });
});
