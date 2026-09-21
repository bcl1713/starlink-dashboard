import { describe, expect, it } from 'vitest';
import config from '../../playwright.config';

function oneWebServer() {
  if (!config.webServer || Array.isArray(config.webServer)) {
    throw new Error('Expected exactly one Playwright webServer configuration');
  }

  return config.webServer;
}

describe('Playwright harness policy', () => {
  it('uses an explicit startup budget and retains no-retry diagnostics', () => {
    expect(oneWebServer()).toMatchObject({
      timeout: expect.any(Number),
    });
    expect(config.use?.trace).toBe('retain-on-failure');
    expect(config.retries).toBe(0);
  });
});
