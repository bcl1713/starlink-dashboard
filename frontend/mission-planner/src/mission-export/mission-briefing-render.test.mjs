import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, mkdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { existsSync } from 'node:fs';
import { createRenderBudget } from './render-budget.mjs';

async function renderer() {
  assert.ok(
    existsSync(new URL('./mission-briefing-render.mjs', import.meta.url)),
    'Mission owner contract absent'
  );
  return (await import('./mission-briefing-render.mjs')).renderMissionBriefing;
}
async function scenario(fault = null) {
  const outputRoot = await mkdtemp(
    path.join(tmpdir(), 'briefing-mission-unit-')
  );
  let clock = 0,
    launches = 0,
    closes = 0;
  const seen = [],
    budget = createRenderBudget({ clock: () => clock });
  const observed = [];
  const observe = async (name) => {
    if (fault !== 'observe-stage') return;
    const record = JSON.parse(
      await readFile(path.join(outputRoot, 'stage-progress.json'), 'utf8')
    );
    assert.equal(record.stage, name);
    assert.equal(record.pid, process.pid);
    assert.equal(record.completed, false);
    observed.push(name);
  };
  let closed;
  const owner = {
    browserIdentity: { version: 'test' },
    close: () =>
      (closed ??= (async () => {
        await observe('teardown');
        closes++;
        clock += 100;
        if (fault === 'cleanup-error')
          throw new Error('Ownership persistence failed');
        return { success: true };
      })()),
  };
  const payload = {
    schemaVersion: 2,
    missionId: 'm',
    snapshotFingerprint: 'f',
    legs: Array.from({ length: 5 }, (_, i) => ({
      legId: 'l' + i,
      mapInput: { id: i },
      mapInputDiagnostics: ['input-' + i],
    })),
  };
  const dependencies = {
    createBudget: () => budget,
    openOwner: async ({ budget: actual }) => {
      await observe('startup');
      seen.push(actual);
      launches++;
      if (fault === 'startup-journal-failure') {
        const journal = path.join(outputRoot, 'stage-progress.json');
        await rm(journal);
        await mkdir(journal);
      }
      return owner;
    },
    mapStage: async ({ budget: actual, input }) => {
      await observe('map:l' + input.id);
      seen.push(actual);
      clock += fault === 'map-cutoff' ? 15000 : 1000;
      return { status: 'primary', pngs: ['map'], warnings: [] };
    },
    documentStage: async ({ budget: actual }) => {
      await observe('document');
      seen.push(actual);
      if (fault === 'cancel-pagination') process.emit('SIGTERM');
      if (fault === 'pagination')
        throw Object.assign(new Error('overflow'), { code: 'overflow' });
      return {
        pagePlan: { pages: [] },
        fit: {},
        expectations: {},
        diagnosticHashes: {},
      };
    },
    printStage: async ({ budget: actual }) => {
      await observe('pdf');
      seen.push(actual);
      clock += 1000;
      return Buffer.from('pdf');
    },
    verifyStage: async ({ budget: actual }) => {
      await observe('verify');
      seen.push(actual);
      actual.workRemainingMs();
      if (fault === 'journal-failure') {
        const journal = path.join(outputRoot, 'stage-progress.json');
        await rm(journal);
        await mkdir(journal);
      }
      if (fault === 'verify-deadline') {
        clock = 58000;
        actual.workRemainingMs();
      }
      return { verified: true };
    },
  };
  try {
    const report = await (
      await renderer()
    )({ payload, outputRoot, assetRoot: outputRoot }, dependencies);
    return {
      report,
      launches,
      closes,
      seen,
      budget,
      observed,
      pdf: await readFile(
        path.join(outputRoot, 'mission-customer-briefing-trial.pdf')
      ).catch(() => null),
    };
  } finally {
    await rm(outputRoot, { recursive: true, force: true });
  }
}
test('one mission one owner and one unchanged budget through maps print verify teardown', async () => {
  const s = await scenario();
  assert.equal(s.report.status, 'success');
  assert.equal(s.launches, 1);
  assert.equal(s.closes, 1);
  assert.equal(s.seen.length, 9);
  assert.ok(s.seen.every((b) => b === s.budget));
  assert.equal(s.report.totalMs, 6100);
  assert.ok(s.pdf);
});
test('shared map reserve skips later legs instead of refreshing allowance', async () => {
  const s = await scenario('map-cutoff');
  assert.equal(s.report.status, 'success');
  assert.equal(s.seen.length, 7);
  assert.equal(s.report.maps.l3.status, 'unavailable');
  assert.deepEqual(s.report.maps.l3.inputDiagnostics, ['input-3']);
  assert.match(s.report.maps.l3.warnings.join(), /reserve/);
});
test('private phase evidence identifies actual active work before observation or cancellation', async () => {
  const s = await scenario('observe-stage');
  assert.equal(s.report.status, 'success');
  assert.deepEqual(s.observed, [
    'startup',
    'map:l0',
    'map:l1',
    'map:l2',
    'map:l3',
    'map:l4',
    'document',
    'pdf',
    'verify',
    'teardown',
  ]);
});
test('failed private journal writes cannot prevent request owner cleanup', async () => {
  const s = await scenario('journal-failure');
  assert.equal(s.closes, 1);
  assert.equal(s.report.cleanup.success, true);
  assert.equal(s.report.status, 'failed');
  assert.equal(s.pdf, null);
});
test('a post-acquisition journal failure still closes the acquired owner', async () => {
  const s = await scenario('startup-journal-failure');
  assert.equal(s.launches, 1);
  assert.equal(s.closes, 1);
  assert.equal(s.report.cleanup.success, true);
  assert.equal(s.report.status, 'failed');
  assert.equal(s.pdf, null);
});
for (const [fault, code] of [
  ['pagination', 'overflow'],
  ['verify-deadline', 'deadline'],
  ['cancel-pagination', 'cancelled'],
  ['cleanup-error', 'cleanup'],
]) {
  test(fault + ' cleans once and removes optional artifacts', async () => {
    const s = await scenario(fault);
    assert.equal(s.report.status, 'failed');
    assert.equal(s.report.errorCode, code);
    assert.equal(s.closes, 1);
    assert.equal(s.pdf, null);
    assert.equal(s.report.artifacts, null);
  });
}
