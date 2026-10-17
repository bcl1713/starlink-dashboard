import { join } from 'node:path';
import { expect, type Page, type Request } from '@playwright/test';
import {
  control,
  evidence,
  mutation,
  noOverflow,
  ready,
  snapshot,
} from './operator-journal-helpers';

export async function failureJourneys(
  phone: Page,
  proof: Record<string, unknown>
) {
  let mediaReadonly = false;
  try {
    // Actual SQLite media permissions fail in backend; no API response is fulfilled.
    await phone.getByRole('button', { name: 'New entry', exact: true }).click();
    await phone
      .getByLabel('Title', { exact: true })
      .fill('Synthetic mobile retained 503 draft');
    const requests: ReturnType<typeof snapshot>[] = [];
    const capture = (request: Request) => {
      if (mutation(request)) requests.push(snapshot(request));
    };
    phone.on('request', capture);
    control('readonly');
    mediaReadonly = true;
    const unavailable = phone.waitForResponse((r) => mutation(r.request()));
    await phone
      .getByRole('button', { name: 'Save entry', exact: true })
      .click();
    const failed = await unavailable;
    expect(failed.status()).toBe(503);
    const failureBody = await failed.json();
    await expect(
      phone.getByRole('alert').filter({ hasText: 'Save outcome is uncertain' })
    ).toBeVisible();
    await expect(phone.getByLabel('Title', { exact: true })).toHaveValue(
      'Synthetic mobile retained 503 draft'
    );
    await expect(phone.getByLabel('Title', { exact: true })).toBeDisabled();
    await noOverflow(phone);
    await phone.screenshot({
      path: join(evidence, 'mobile-390x844-error.png'),
      fullPage: true,
    });
    control('writable');
    mediaReadonly = false;
    control('restart');
    await ready(phone);
    const recovered = phone.waitForResponse((r) => mutation(r.request()));
    await phone.getByRole('button', { name: 'Retry exact save' }).click();
    expect((await recovered).ok()).toBeTruthy();
    await expect(
      phone.getByRole('heading', { name: 'Edit entry · version 1' })
    ).toBeVisible();
    phone.off('request', capture);
    expect(requests).toHaveLength(2);
    expect(requests[1]).toEqual(requests[0]);
    const mediaCounts = JSON.parse(control('counts', requests[0].key));
    expect(mediaCounts).toEqual({ receipts: 1, revisions: 1 });
    proof.actualMedia503 = {
      requests,
      failureBody,
      counts: mediaCounts,
      retainedDraft: true,
    };

    // Deliberately lose acknowledgment AFTER real backend commit; distinct from media 503.
    await phone.getByRole('button', { name: 'New entry', exact: true }).click();
    await phone
      .getByLabel('Title', { exact: true })
      .fill('Synthetic lost acknowledgment');
    const lossRequests: ReturnType<typeof snapshot>[] = [];
    phone.on('request', (request) => {
      if (mutation(request)) lossRequests.push(snapshot(request));
    });
    let intercepted = false;
    await phone.route('**/api/v2/operator/records', async (route) => {
      if (route.request().method() !== 'POST' || intercepted)
        return route.continue();
      intercepted = true;
      const committed = await route.fetch();
      expect(committed.ok()).toBeTruthy();
      await route.abort('connectionreset');
    });
    await phone
      .getByRole('button', { name: 'Save entry', exact: true })
      .click();
    await expect(
      phone.getByRole('button', { name: 'Retry exact save' })
    ).toBeVisible();
    expect(JSON.parse(control('counts', lossRequests[0].key))).toEqual({
      receipts: 1,
      revisions: 1,
    });
    await phone.unroute('**/api/v2/operator/records');
    await phone.getByRole('button', { name: 'Retry exact save' }).click();
    await expect(
      phone.getByRole('heading', { name: 'Edit entry · version 1' })
    ).toBeVisible();
    expect(lossRequests).toHaveLength(2);
    expect(lossRequests[1]).toEqual(lossRequests[0]);
    expect(JSON.parse(control('counts', lossRequests[0].key))).toEqual({
      receipts: 1,
      revisions: 1,
    });
    proof.browserResponseLossInjection = {
      mechanism:
        'route.fetch committed backend then route.abort acknowledgment',
      requests: lossRequests,
      onePersistedRevision: true,
    };
  } finally {
    if (mediaReadonly) control('writable');
  }
}
