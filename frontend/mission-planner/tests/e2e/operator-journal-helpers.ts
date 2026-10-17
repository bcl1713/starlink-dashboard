import { execFileSync } from 'node:child_process';
import { join } from 'node:path';
import { expect, type Page, type Request, type Route } from '@playwright/test';

export const evidence = process.env.OPERATOR_ACCEPTANCE_EVIDENCE!;
export const origin = process.env.OPERATOR_ACCEPTANCE_ORIGIN!;
export const journal = '/operator?mission_id=synthetic-mission-a';
export function control(action: string, key?: string): string {
  return execFileSync(
    'python3',
    [
      join(
        process.env.OPERATOR_SOURCE_ROOT!,
        'tools/acceptance/operator-journal/browser_control.py'
      ),
      action,
      ...(key ? [key] : []),
    ],
    { env: process.env, encoding: 'utf8', timeout: 70_000 }
  );
}
export function mutation(request: Request) {
  return (
    request.url().includes('/api/v2/operator/records') &&
    ['POST', 'PUT'].includes(request.method())
  );
}
export function snapshot(request: Request) {
  return {
    key: request.headers()['idempotency-key'],
    epoch: request.headers()['x-operator-store-epoch'],
    body: request.postData(),
    method: request.method(),
    url: request.url(),
  };
}
export async function save(page: Page, holdReceipt = false) {
  let release!: () => void;
  let received!: () => void;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  const realResponse = new Promise<void>((resolve) => {
    received = resolve;
  });
  const handler = async (route: Route) => {
    if (!mutation(route.request())) return route.fallback();
    const result = await route.fetch();
    received();
    await held;
    await route.fulfill({ response: result });
  };
  if (holdReceipt) await page.route('**/api/v2/operator/records**', handler);
  const response = page.waitForResponse((r) => mutation(r.request()));
  await page.getByRole('button', { name: 'Save entry', exact: true }).click();
  if (holdReceipt) {
    try {
      await realResponse;
      await expect(page.getByRole('status')).toHaveText('Saving…');
      await expect(
        page.getByRole('button', { name: 'Save entry', exact: true })
      ).toBeDisabled();
    } finally {
      release();
    }
  }
  const result = await response;
  if (holdReceipt) await page.unroute('**/api/v2/operator/records**', handler);
  expect(result.ok()).toBeTruthy();
  const receipt = await result.json();
  await expect(
    page.getByRole('heading', {
      name: `Edit entry · version ${receipt.saved_records[0].version}`,
    })
  ).toBeVisible();
  await expect(page.getByRole('status')).toHaveText('Saved.');
  return receipt.saved_records[0];
}
export async function noOverflow(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth
    )
  ).toBeTruthy();
}
export async function ready(page: Page) {
  await expect
    .poll(
      async () => {
        try {
          return (
            await page.request.get(`${origin}/api/v2/operator/health`)
          ).status();
        } catch {
          return 0;
        }
      },
      { timeout: 60_000 }
    )
    .toBe(200);
}
