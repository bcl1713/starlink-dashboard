import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test, type Page } from '@playwright/test';
import { snapshot } from './operator-journal-helpers';
import { observeOverviewCamera } from './support/overview-camera';

const root = process.env.OPERATOR_ACCEPTANCE_EVIDENCE!;
const mode = process.env.OPERATOR_RELEASE_MODE;
const fixtures = JSON.parse(
  readFileSync(process.env.OPERATOR_WORKSPACE_INPUTS!, 'utf8')
) as { seed: string; mission: { id: string } }[];
function saveReport(section: string, value: unknown) {
  const path = join(root, 'workspace-release.json');
  const previous = existsSync(path)
    ? JSON.parse(readFileSync(path, 'utf8'))
    : { synthetic: true, mode };
  writeFileSync(
    path,
    JSON.stringify({ ...previous, [section]: value }, null, 2)
  );
}

test('release gate: retained drafts and uncertain command remain recoverable through whole-shell backout', async ({
  browser,
}) => {
  test.skip(
    mode !== 'candidate',
    'Original baseline has no candidate draft envelopes'
  );
  const missionId = fixtures.find((f) => f.seed === 'normal')!.mission.id;
  const proofs = [];
  for (const viewport of [
    { width: 1920, height: 1080 },
    { width: 390, height: 844 },
    { width: 844, height: 390 },
  ]) {
    const context = await browser.newContext({ viewport });
    try {
      const page = await context.newPage();
      await page.goto(`/operator?workspace=1&mission_id=${missionId}`);
      await expect(
        page.getByRole('navigation', { name: 'Operator workspace' })
      ).toBeVisible();
      const parked = `Backout parked ${viewport.width}`;
      const uncertain = `Backout uncertain ${viewport.width}`;
      const openNote = async (title: string) => {
        await page.getByRole('button', { name: 'Note', exact: true }).click();
        const editor = page.getByRole('dialog');
        await editor.getByLabel('Title', { exact: true }).fill(title);
        await editor
          .getByRole('textbox', { name: 'Note', exact: true })
          .fill('Fictional retained input before backout');
        return editor;
      };
      const first = await openNote(parked);
      await first
        .getByRole('button', { name: 'Keep draft and return', exact: true })
        .click();
      let originalReceipt: unknown;
      const attempts: ReturnType<typeof snapshot>[] = [];
      let dropped = false;
      await page.route('**/api/v2/operator/records', async (route) => {
        if (route.request().method() !== 'POST') return route.continue();
        attempts.push(snapshot(route.request()));
        if (dropped) return route.continue();
        dropped = true;
        const response = await route.fetch();
        expect(response.ok()).toBe(true);
        originalReceipt = await response.json();
        await route.abort('connectionreset');
      });
      const editor = await openNote(uncertain);
      await editor
        .getByRole('button', { name: 'Save entry', exact: true })
        .click();
      await expect(editor).toContainText(/uncertain/i);
      await editor
        .getByRole('button', { name: 'Keep draft and return', exact: true })
        .click();
      const read = async () =>
        (
          await page.request.get(
            `/api/v2/operator/records?mission_id=${missionId}`
          )
        ).json();
      const before = await read();
      // No new submission is made during backout. Navigate the entire original
      // shell and reload; do not rewrite, downgrade or substitute its store.
      await page.goto(`/operator?mission_id=${missionId}`);
      await page.reload();
      await expect(
        page.getByRole('heading', { name: 'Operator journal', exact: true })
      ).toBeVisible();
      const notice = page.getByRole('complementary', {
        name: 'Retained workspace work',
        exact: true,
      });
      await expect(notice).toContainText('drafts or saves are retained');
      await expect(
        page.getByRole('navigation', { name: 'Operator workspace' })
      ).toHaveCount(0);
      const backedOut = await read();
      expect(backedOut.H).toBe(before.H);
      expect(backedOut.items.map((i: { record: unknown }) => i.record)).toEqual(
        before.items.map((i: { record: unknown }) => i.record)
      );
      expect(attempts).toHaveLength(1);
      await notice
        .getByRole('link', {
          name: 'Open retained drafts and save status',
          exact: true,
        })
        .click();
      await expect(
        page.getByRole('region', { name: 'Save status', exact: true })
      ).toContainText(`${uncertain} · uncertain`);
      const retained = page.getByRole('region', {
        name: 'Retained drafts',
        exact: true,
      });
      await expect(
        retained.getByRole('button', { name: new RegExp(parked) })
      ).toBeVisible();
      const response = page.waitForResponse(
        (r) =>
          r.request().method() === 'POST' &&
          r.url().endsWith('/api/v2/operator/records')
      );
      const retry = page.getByRole('button', {
        name: 'Retry same save',
        exact: true,
      });
      await expect(retry).toBeEnabled();
      await retry.click();
      const accepted = await response;
      expect(accepted.ok()).toBe(true);
      const receipt = await accepted.json();
      expect(receipt).toEqual(originalReceipt);
      expect(attempts).toHaveLength(2);
      expect(attempts[1]).toEqual(attempts[0]);
      await expect(retry).toHaveCount(0);
      const history = await (
        await page.request.get(
          `/api/v2/operator/records/${receipt.saved_records[0].record_id}/history`
        )
      ).json();
      expect(history.items).toHaveLength(1);
      expect(history.cursor).toBeNull();
      const after = await read();
      expect(after.H).toBe(before.H);
      expect(
        after.items.some(
          (i: { record: { payload: { title: string } } }) =>
            i.record.payload.title === parked
        )
      ).toBe(false);
      await page.goto(`/operator?mission_id=${missionId}`);
      await page
        .getByRole('complementary', {
          name: 'Retained workspace work',
          exact: true,
        })
        .getByRole('link', {
          name: 'Open retained drafts and save status',
          exact: true,
        })
        .click();
      await page
        .getByRole('region', { name: 'Retained drafts', exact: true })
        .getByRole('button', { name: new RegExp(parked) })
        .click();
      await expect(
        page.getByRole('dialog').getByLabel('Title', { exact: true })
      ).toHaveValue(parked);
      await expect(
        page
          .getByRole('dialog')
          .getByRole('textbox', { name: 'Note', exact: true })
      ).toHaveValue('Fictional retained input before backout');
      proofs.push({
        viewport,
        beforeH: before.H,
        afterH: after.H,
        attempts,
        receipt,
        history,
        pendingSurvivedOriginalShellReload: true,
        parkedInputRetained: true,
        noStoreRewrite: true,
      });
      saveReport('backout', proofs);
    } finally {
      await context.close();
    }
  }
});

type ProfileWindow = Window & {
  __operatorReleaseCommits?: number;
  __REACT_DEVTOOLS_GLOBAL_HOOK__?: {
    onCommitFiberRoot: (...args: unknown[]) => void;
  };
  __overviewEvidenceRoots?: {
    containerInfo?: {
      getState?: () => {
        gl: {
          domElement: HTMLCanvasElement;
          info: { render: { frame: number } };
        };
      };
    };
  }[];
};
async function observedRender(page: Page) {
  return page.evaluate(() => {
    const observed = window as ProfileWindow;
    const state = observed.__overviewEvidenceRoots
      ?.find((r) => r.containerInfo?.getState?.().gl.domElement.isConnected)
      ?.containerInfo?.getState?.();
    return {
      commits: observed.__operatorReleaseCommits ?? 0,
      frame: state?.gl.info.render.frame ?? null,
      visible: document.visibilityState,
    };
  });
}

test('release gate: sixty-second foreground CPU, render commits and polling traces', async ({
  browser,
}) => {
  test.skip(!mode, 'Only the owned release runner selects profiling');
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
  });
  const profiles = [];
  const missionId = fixtures.find((f) => f.seed === 'busy')!.mission.id;
  try {
    const page = await context.newPage();
    await observeOverviewCamera(page);
    for (const [name, url] of [
      [
        'operator',
        `/operator?${mode === 'candidate' ? 'workspace=1&' : ''}mission_id=${missionId}`,
      ],
      ['overview', '/overview'],
    ] as const) {
      await page.goto(url);
      await page.bringToFront();
      if (name === 'operator') {
        if (mode === 'candidate')
          await expect(
            page.getByRole('region', { name: 'Next requirement', exact: true })
          ).toBeVisible();
        else
          await expect(
            page
              .getByRole('region', { name: 'Communications', exact: true })
              .getByRole('heading', {
                name: 'Synthetic customer 1',
                exact: true,
              })
          ).toBeVisible();
      } else
        await page.waitForFunction(() =>
          (window as ProfileWindow).__overviewEvidenceRoots?.some(
            (r) => r.containerInfo?.getState?.().gl.domElement.isConnected
          )
        );
      // Fixed warm-up and sampling intervals are measurements required by the
      // approved performance plan, not readiness substitutes for assertions.
      await page.waitForTimeout(2000);
      await page.evaluate(() => {
        const observed = window as ProfileWindow;
        const hook = observed.__REACT_DEVTOOLS_GLOBAL_HOOK__;
        if (!hook) throw new Error('Actual React commit observer missing');
        const original = hook.onCommitFiberRoot;
        observed.__operatorReleaseCommits = 0;
        hook.onCommitFiberRoot = (...args) => {
          observed.__operatorReleaseCommits!++;
          original(...args);
        };
      });
      const counts: Record<string, number> = {};
      const onRequest = (request: import('@playwright/test').Request) => {
        const path = new URL(request.url()).pathname;
        if (path.startsWith('/api/')) counts[path] = (counts[path] ?? 0) + 1;
      };
      const cdp = await context.newCDPSession(page);
      let running = false;
      try {
        await cdp.send('Performance.enable');
        await cdp.send('Profiler.enable');
        await cdp.send('Profiler.setSamplingInterval', { interval: 10000 });
        const before = await cdp.send('Performance.getMetrics');
        const renderBefore = await observedRender(page);
        expect(renderBefore.visible).toBe('visible');
        page.on('request', onRequest);
        await cdp.send('Profiler.start');
        running = true;
        const started = performance.now();
        await page.waitForTimeout(60000);
        const elapsedMs = performance.now() - started;
        const { profile } = await cdp.send('Profiler.stop');
        running = false;
        page.off('request', onRequest);
        const after = await cdp.send('Performance.getMetrics');
        const renderAfter = await observedRender(page);
        const values = (v: { metrics: { name: string; value: number }[] }) =>
          Object.fromEntries(v.metrics.map((m) => [m.name, m.value]));
        const a = values(after),
          b = values(before);
        const profileFile = `${mode}-${name}-cpu-profile.json`;
        writeFileSync(join(root, profileFile), JSON.stringify(profile));
        const result = {
          page: name,
          elapsedMs,
          profileFile,
          samplingIntervalUs: 10000,
          metricBefore: b,
          metricAfter: a,
          taskDurationSeconds: a.TaskDuration - b.TaskDuration,
          scriptDurationSeconds: a.ScriptDuration - b.ScriptDuration,
          renderBefore,
          renderAfter,
          requestCounts: counts,
          scope:
            'Same machine; real production browser. CPU profiles and React commits are observation only; no physical GPU or human inference.',
        };
        profiles.push(result);
        saveReport('idleProfiles', profiles);
        expect(elapsedMs).toBeGreaterThanOrEqual(60000);
        expect(renderAfter.visible).toBe('visible');
        if (mode === 'candidate') {
          expect(counts['/api/v2/operator/health'] ?? 0).toBeLessThanOrEqual(5);
          expect(counts['/api/v2/operator/events'] ?? 0).toBeLessThanOrEqual(
            name === 'operator' ? 5 : 0
          );
          expect(counts['/api/v2/operator/records'] ?? 0).toBeLessThanOrEqual(
            1
          );
          expect(counts['/api/overview-links/presets'] ?? 0).toBe(0);
        }
      } finally {
        page.off('request', onRequest);
        if (running) await cdp.send('Profiler.stop').catch(() => {});
        await cdp.detach();
      }
    }
  } finally {
    await context.close();
  }
});
